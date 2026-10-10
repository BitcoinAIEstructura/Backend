"""Backtesting: simula una estrategia sobre velas históricas, solo con posiciones largas."""

from dataclasses import dataclass

from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estrategia.modelo import Decision, Senal
from bitcoinai.estructuras import Lista, ListaDoble, Pila
from bitcoinai.indicadores import PuntoIndicador, Serie, maxima_caida_de_puntos
from bitcoinai.modelo import Vela

DECISIONES_RECIENTES = 20
"""Cuántas decisiones de comprar o vender se devuelven en el resultado."""


@dataclass(frozen=True, slots=True)
class OperacionCerrada:
    """Una operación larga completa: compra y luego venta.

    Atributos:
        tiempo_entrada / precio_entrada: vela y precio (apertura) de la compra.
        tiempo_salida / precio_salida: vela y precio de la venta.
        cantidad_btc: BTC comprados (ya descontada la comisión de compra).
        comisiones: comisiones de compra y venta, en USDT.
        ganancia: capital al salir − capital al entrar (negativa si hubo pérdida).
        rentabilidad: ganancia / capital al entrar (0,05 = 5 %).
        motivo_salida: por qué se vendió.
    """

    tiempo_entrada: int
    precio_entrada: float
    tiempo_salida: int
    precio_salida: float
    cantidad_btc: float
    comisiones: float
    ganancia: float
    rentabilidad: float
    motivo_salida: str


@dataclass(frozen=True, slots=True)
class ResultadoBacktest:
    """Resultado y métricas de un backtest.

    Las rentabilidades, la tasa de aciertos y la caída son fracciones (0,25 = 25 %).
    ``factor_beneficio`` es ganancias / pérdidas, o None si no hubo pérdidas.
    ``decisiones_recientes`` son las últimas decisiones de comprar o vender, la
    más reciente primero; ``curva_capital`` es el valor de la cartera al cierre de
    cada vela operada.
    """

    estrategia: str
    parametros: dict[str, object]
    capital_inicial: float
    comision: float
    capital_final: float
    rentabilidad_total: float
    rentabilidad_comprar_y_mantener: float
    numero_operaciones: int
    tasa_ganadoras: float
    caida_maxima: float
    factor_beneficio: float | None
    comisiones_pagadas: float
    velas_analizadas: int
    numero_decisiones: int
    tiempo_inicio: int
    tiempo_fin: int
    operaciones: Lista[OperacionCerrada]
    decisiones_recientes: Lista[Decision]
    curva_capital: Serie


class Backtester:
    """Simula una estrategia sobre velas históricas, solo con posiciones largas.

    Reglas:
        - **Sin mirar el futuro:** se recorre la ListaDoble de la vela más antigua a
          la más reciente; en cada una la estrategia recibe una lista que contiene
          solo las velas hasta esa (se le van agregando al final, una por vuelta).
        - **Ejecución honesta:** la estrategia decide con el cierre de la vela t, y
          la orden se ejecuta en la apertura de la vela t + 1. Una señal en la
          última vela no llega a ejecutarse.
        - COMPRAR sin posición compra con todo el efectivo; VENDER con posición vende
          todo. Las demás señales se ignoran.
        - Cada compra y cada venta paga la comisión sobre el monto operado.
        - Si al final queda una posición abierta, se cierra al último cierre.

    Cada decisión se apila en una Pila (la más reciente arriba) y cada operación
    cerrada se agrega a una Lista.
    Complejidad: O(n · E), donde E es el costo de evaluar la estrategia. Como el
    backtest le entrega siempre la misma lista con una vela más, las estrategias
    usan su memoria incremental y E es O(1): el backtest completo es O(n).
    """

    def __init__(self, capital_inicial: float = 1000, comision: float = 0.001) -> None:
        """Raises: ValueError si el capital no es positivo o la comisión no está en [0, 1)."""
        if not 0 < capital_inicial < float("inf"):
            raise ValueError(f"El capital inicial debe ser positivo: {capital_inicial}")
        if not 0 <= comision < 1:
            raise ValueError(f"La comisión debe estar entre 0 y 1: {comision}")
        self.capital_inicial = float(capital_inicial)
        self.comision = float(comision)

    def ejecutar(
        self, estrategia: Estrategia, velas: ListaDoble[Vela], inicio_operaciones: int = 0
    ) -> ResultadoBacktest:
        """Ejecuta el backtest operando solo desde la vela ``inicio_operaciones``.

        Las velas anteriores se entregan a la estrategia como historial (para
        calentar sus indicadores), pero en ellas no se decide ni se opera.

        Raises:
            ValueError: si el índice está fuera de rango.
        """
        if not 0 <= inicio_operaciones <= velas.tamanio():
            raise ValueError(f"inicio_operaciones fuera de rango: {inicio_operaciones}")

        hasta_ahora: ListaDoble[Vela] = ListaDoble()
        decisiones: Pila[Decision] = Pila()
        curva: Serie = ListaDoble()
        cuenta = _Cuenta(self.capital_inicial, self.comision)
        pendiente: Decision | None = None
        primera: Vela | None = None
        ultima: Vela | None = None

        for indice, vela in enumerate(velas):
            hasta_ahora.agregar_final(vela)
            if indice < inicio_operaciones:
                continue  # solo historial
            if primera is None:
                primera = vela
            ultima = vela

            # 1) La orden decidida en la vela anterior se ejecuta en la apertura de esta.
            if pendiente is not None:
                if pendiente.senal is Senal.COMPRAR and not cuenta.en_posicion:
                    cuenta.comprar(vela.tiempo_apertura, vela.apertura)
                elif pendiente.senal is Senal.VENDER and cuenta.en_posicion:
                    cuenta.vender(vela.tiempo_apertura, vela.apertura, pendiente.motivo)
                pendiente = None

            # 2) La estrategia decide viendo solo las velas hasta esta.
            decision = estrategia.evaluar(hasta_ahora)
            decisiones.apilar(decision)
            if decision.senal is not Senal.MANTENER:
                pendiente = decision
            curva.agregar_final(PuntoIndicador(vela.tiempo_apertura, cuenta.valor(vela.cierre)))

        if cuenta.en_posicion and ultima is not None:
            cuenta.vender(ultima.tiempo_apertura, ultima.cierre, "Cierre forzado al final del periodo.")
        return self._armar_resultado(estrategia, cuenta, decisiones, curva, primera, ultima)

    def _armar_resultado(self, estrategia: Estrategia, cuenta: "_Cuenta", decisiones: Pila[Decision],
                         curva: Serie, primera: Vela | None, ultima: Vela | None) -> ResultadoBacktest:
        ganadoras = 0
        suma_ganancias = 0.0
        suma_perdidas = 0.0
        for operacion in cuenta.operaciones:
            if operacion.ganancia > 0:
                ganadoras += 1
                suma_ganancias += operacion.ganancia
            else:
                suma_perdidas -= operacion.ganancia
        numero = cuenta.operaciones.tamanio()

        comprar_y_mantener = 0.0
        if primera is not None and ultima is not None:
            comprar_y_mantener = (1 - self.comision) ** 2 * ultima.cierre / primera.apertura - 1

        # La pila deja la decisión más reciente arriba: al desapilar salen de la
        # más nueva a la más vieja, que es justo el orden que interesa mostrar.
        numero_decisiones = decisiones.tamanio()
        recientes: Lista[Decision] = Lista()
        while not decisiones.esta_vacia() and recientes.tamanio() < DECISIONES_RECIENTES:
            decision = decisiones.desapilar()
            if decision.senal is not Senal.MANTENER:
                recientes.agregar(decision)

        return ResultadoBacktest(
            estrategia=estrategia.nombre(),
            parametros=estrategia.parametros(),
            capital_inicial=self.capital_inicial,
            comision=self.comision,
            capital_final=cuenta.efectivo,
            rentabilidad_total=cuenta.efectivo / self.capital_inicial - 1,
            rentabilidad_comprar_y_mantener=comprar_y_mantener,
            numero_operaciones=numero,
            tasa_ganadoras=ganadoras / numero if numero else 0.0,
            caida_maxima=maxima_caida_de_puntos(curva).caida_maxima,
            factor_beneficio=None if suma_perdidas == 0 else suma_ganancias / suma_perdidas,
            comisiones_pagadas=cuenta.comisiones,
            velas_analizadas=curva.tamanio(),
            numero_decisiones=numero_decisiones,
            tiempo_inicio=primera.tiempo_apertura if primera is not None else 0,
            tiempo_fin=ultima.tiempo_cierre if ultima is not None else 0,
            operaciones=cuenta.operaciones,
            decisiones_recientes=recientes,
            curva_capital=curva,
        )


class _Cuenta:
    """Estado de la cuenta simulada: efectivo, BTC y la operación abierta."""

    def __init__(self, capital: float, comision: float) -> None:
        self.efectivo = capital
        self.comision = comision
        self.btc = 0.0
        self.en_posicion = False
        self.comisiones = 0.0
        self.capital_al_entrar = 0.0
        self.comision_entrada = 0.0
        self.precio_entrada = 0.0
        self.tiempo_entrada = 0
        self.operaciones: Lista[OperacionCerrada] = Lista()

    def valor(self, precio: float) -> float:
        return self.efectivo + self.btc * precio

    def comprar(self, tiempo: int, precio: float) -> None:
        self.capital_al_entrar = self.efectivo
        self.comision_entrada = self.efectivo * self.comision
        self.btc = (self.efectivo - self.comision_entrada) / precio
        self.efectivo = 0.0
        self.comisiones += self.comision_entrada
        self.precio_entrada = precio
        self.tiempo_entrada = tiempo
        self.en_posicion = True

    def vender(self, tiempo: int, precio: float, motivo: str) -> None:
        bruto = self.btc * precio
        comision_salida = bruto * self.comision
        self.efectivo = bruto - comision_salida
        self.comisiones += comision_salida
        ganancia = self.efectivo - self.capital_al_entrar
        self.operaciones.agregar(OperacionCerrada(
            self.tiempo_entrada, self.precio_entrada, tiempo, precio, self.btc,
            self.comision_entrada + comision_salida, ganancia, ganancia / self.capital_al_entrar, motivo))
        self.btc = 0.0
        self.en_posicion = False
