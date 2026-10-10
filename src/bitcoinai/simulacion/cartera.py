"""Cartera simulada: saldo en USDT, BTC y costo de la posición."""

import math
from dataclasses import dataclass

from bitcoinai.simulacion.interfaces import DatosCartera
from bitcoinai.simulacion.modelo import OperacionRechazadaError

SALDO_INICIAL_POR_DEFECTO = 10_000.0
"""Saldo inicial por defecto, en USDT."""

_TOLERANCIA = 1e-9
"""Diferencias menores que esto se consideran redondeo."""


@dataclass(frozen=True, slots=True)
class Ejecucion:
    """Resultado de ejecutar una operación.

    Atributos:
        monto_usdt: USDT pagados (compra) o brutos obtenidos (venta).
        cantidad_btc: BTC recibidos o entregados.
        comision: comisión cobrada en USDT.
    """

    monto_usdt: float
    cantidad_btc: float
    comision: float


@dataclass(frozen=True, slots=True)
class EstadoCartera:
    """Foto de la cartera valorada a un precio.

    ``costo_promedio`` incluye las comisiones de compra (0 si no hay BTC);
    ``ganancia_total`` es ``valor_total − saldo_inicial`` y ``rentabilidad`` es
    esa ganancia dividida entre el saldo inicial (0,05 = 5 %).
    """

    precio_actual: float
    saldo_usdt: float
    btc: float
    costo_promedio: float
    valor_btc: float
    valor_total: float
    ganancia_no_realizada: float
    ganancia_realizada: float
    ganancia_total: float
    rentabilidad: float
    comisiones_pagadas: float
    saldo_inicial: float


class Cartera:
    """Cartera simulada.

    Contabilidad:
        - **Compra** de M USDT al precio P con comisión c: se pagan M USDT, la
          comisión es M·c y se reciben (M − M·c) / P BTC. El costo de la posición
          aumenta en M (la comisión forma parte del costo).
        - **Venta** de B BTC al precio P: se obtienen B·P USDT brutos, se paga B·P·c
          de comisión y se recibe el resto. El costo de la posición baja en
          proporción a lo vendido, así que el costo promedio no cambia. La ganancia
          realizada es lo recibido menos el costo de lo vendido.

    No es segura para varios hilos: la protege el ``LibroDeOrdenes``.
    Todas las operaciones son O(1).
    """

    def __init__(self, saldo_inicial: float = SALDO_INICIAL_POR_DEFECTO) -> None:
        """Raises: ValueError si el saldo inicial no es positivo."""
        if not (saldo_inicial > 0 and math.isfinite(saldo_inicial)):
            raise ValueError(f"El saldo inicial debe ser positivo: {saldo_inicial}")
        self.saldo_inicial = float(saldo_inicial)
        self.saldo_usdt = float(saldo_inicial)
        self.btc = 0.0
        self.costo_posicion = 0.0
        self.ganancia_realizada = 0.0
        self.comisiones_pagadas = 0.0

    @classmethod
    def desde_datos(cls, datos: DatosCartera) -> "Cartera":
        """Reconstruye una cartera guardada."""
        cartera = cls(datos.saldo_inicial)
        cartera.saldo_usdt = datos.saldo_usdt
        cartera.btc = datos.btc
        cartera.costo_posicion = datos.costo_posicion if datos.btc > 0 else 0.0
        cartera.ganancia_realizada = datos.ganancia_realizada
        cartera.comisiones_pagadas = datos.comisiones_pagadas
        return cartera

    def datos(self) -> DatosCartera:
        """Los datos necesarios para reconstruirla. Complejidad: O(1)."""
        return DatosCartera(self.saldo_inicial, self.saldo_usdt, self.btc, self.costo_posicion,
                            self.ganancia_realizada, self.comisiones_pagadas)

    def comprar(self, monto_usdt: float, precio: float, comision: float) -> Ejecucion:
        """Compra BTC por un monto en USDT (comisión incluida).

        Raises:
            OperacionRechazadaError: si no alcanza el saldo.
        """
        if monto_usdt > self.saldo_usdt + _TOLERANCIA:
            raise OperacionRechazadaError(
                f"Saldo insuficiente: la compra necesita {monto_usdt:.2f} USDT y hay {self.saldo_usdt:.2f}")
        costo_comision = monto_usdt * comision
        comprado = (monto_usdt - costo_comision) / precio
        self.saldo_usdt = max(0.0, self.saldo_usdt - monto_usdt)
        self.btc += comprado
        self.costo_posicion += monto_usdt
        self.comisiones_pagadas += costo_comision
        return Ejecucion(monto_usdt, comprado, costo_comision)

    def vender(self, monto_usdt: float, precio: float, comision: float) -> Ejecucion:
        """Vende BTC por un monto en USDT (brutos, antes de comisión).

        Raises:
            OperacionRechazadaError: si no hay BTC suficiente.
        """
        cantidad = monto_usdt / precio
        if cantidad > self.btc + _TOLERANCIA:
            raise OperacionRechazadaError(
                f"BTC insuficiente: la venta necesita {cantidad:.8f} BTC y hay {self.btc:.8f}")
        return self._vender_cantidad(min(cantidad, self.btc), precio, comision)

    def vender_todo(self, precio: float, comision: float) -> Ejecucion:
        """Vende todo el BTC.

        Raises:
            OperacionRechazadaError: si no hay BTC.
        """
        if self.btc <= 0:
            raise OperacionRechazadaError("No hay BTC para vender")
        return self._vender_cantidad(self.btc, precio, comision)

    def _vender_cantidad(self, cantidad: float, precio: float, comision: float) -> Ejecucion:
        bruto = cantidad * precio
        costo_comision = bruto * comision
        costo_vendido = self.costo_posicion * (cantidad / self.btc)
        self.saldo_usdt += bruto - costo_comision
        self.ganancia_realizada += bruto - costo_comision - costo_vendido
        self.comisiones_pagadas += costo_comision
        self.btc -= cantidad
        self.costo_posicion -= costo_vendido
        if self.btc < _TOLERANCIA * 1e-3:  # restos de redondeo
            self.btc = 0.0
            self.costo_posicion = 0.0
        return Ejecucion(bruto, cantidad, costo_comision)

    def costo_promedio(self) -> float:
        """USDT pagados por BTC en la posición actual, con comisiones (0 si no hay BTC)."""
        return self.costo_posicion / self.btc if self.btc > 0 else 0.0

    def valor_total(self, precio: float) -> float:
        """Saldo en USDT más el valor del BTC al precio dado."""
        return self.saldo_usdt + self.btc * precio

    def ganancia_total(self, precio: float) -> float:
        """Valor total − saldo inicial (negativo si hay pérdida)."""
        return self.valor_total(precio) - self.saldo_inicial

    def ganancia_no_realizada(self, precio: float) -> float:
        """Valor del BTC − lo que costó."""
        return self.btc * precio - self.costo_posicion

    def estado(self, precio: float) -> EstadoCartera:
        """Foto completa de la cartera valorada al precio dado."""
        ganancia = self.ganancia_total(precio)
        return EstadoCartera(precio, self.saldo_usdt, self.btc, self.costo_promedio(), self.btc * precio,
                             self.valor_total(precio), self.ganancia_no_realizada(precio), self.ganancia_realizada,
                             ganancia, ganancia / self.saldo_inicial, self.comisiones_pagadas, self.saldo_inicial)
