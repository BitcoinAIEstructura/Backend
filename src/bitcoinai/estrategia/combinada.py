"""Estrategia combinada por votación ponderada."""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from bitcoinai.estrategia import apoyo
from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estrategia.cruce import CruceDeMedias
from bitcoinai.estrategia.macd import EstrategiaMacd
from bitcoinai.estrategia.modelo import Decision, Senal
from bitcoinai.estrategia.rsi import EstrategiaRsi
from bitcoinai.estructuras import Lista, ListaDoble
from bitcoinai.modelo import Vela


@dataclass(frozen=True, slots=True)
class Componente:
    """Una estrategia con su peso en la votación (0 o más)."""

    estrategia: Estrategia
    peso: float

    def __post_init__(self) -> None:
        """Raises: ValueError si el peso es negativo o no es finito."""
        if not (self.peso >= 0 and math.isfinite(self.peso)):
            raise ValueError(f"El peso debe ser un número de 0 o más: {self.peso}")


class EstrategiaCombinada(Estrategia):
    """Combina varias estrategias por votación ponderada.

    Cada estrategia vota su señal con un peso igual a peso × confianza. El
    puntaje de cada señal es la suma de sus votos dividida entre la suma de los
    pesos (queda entre 0 y 1). Gana la señal con mayor puntaje, y ese puntaje es
    la confianza. Desempates, por prudencia: si empatan MANTENER y otra, gana
    MANTENER; si empatan COMPRAR y VENDER, las estrategias se contradicen y se
    devuelve MANTENER.

    Por defecto combina CruceDeMedias, EstrategiaRsi y EstrategiaMacd con peso 1.
    Complejidad de ``evaluar``: la suma de las de sus componentes, O(n).
    """

    def __init__(self, componentes: Iterable[Componente] | None = None) -> None:
        """Raises: ValueError si no hay componentes o todos los pesos son 0."""
        if componentes is None:
            componentes = (Componente(CruceDeMedias(), 1), Componente(EstrategiaRsi(), 1),
                           Componente(EstrategiaMacd(), 1))
        self._componentes: Lista[Componente] = Lista()
        suma = 0.0
        for componente in componentes:
            self._componentes.agregar(componente)
            suma += componente.peso
        if self._componentes.esta_vacia() or not suma > 0:
            raise ValueError("La estrategia combinada necesita al menos un peso mayor que 0")
        self._suma_pesos = suma
        super().__init__()

    @classmethod
    def con_pesos(cls, peso_cruce: float, peso_rsi: float, peso_macd: float) -> "EstrategiaCombinada":
        """Cruce, RSI y MACD con sus parámetros por defecto y los pesos dados."""
        return cls((Componente(CruceDeMedias(), peso_cruce), Componente(EstrategiaRsi(), peso_rsi),
                    Componente(EstrategiaMacd(), peso_macd)))

    def nombre(self) -> str:
        return "combinada"

    def parametros(self) -> dict[str, object]:
        pesos: dict[str, object] = {}
        estrategias: dict[str, object] = {}
        for componente in self._componentes:
            pesos[componente.estrategia.nombre()] = componente.peso
            estrategias[componente.estrategia.nombre()] = componente.estrategia.parametros()
        return {"pesos": pesos, "estrategias": estrategias}

    def velas_minimas(self) -> int:
        return max(c.estrategia.velas_minimas() for c in self._componentes)

    def evaluar_componentes(self, velas: ListaDoble[Vela]) -> dict[str, Decision]:
        """La decisión de cada componente por separado, en orden."""
        return {c.estrategia.nombre(): c.estrategia.evaluar(velas) for c in self._componentes}

    def evaluar(self, velas_hasta_ahora: ListaDoble[Vela] | None) -> Decision:
        """Votación de las componentes (cada una con su memoria incremental).

        Basta con que una componente pueda opinar; si ninguna puede, faltan velas.
        """
        minimo_para_opinar = min(c.estrategia.velas_minimas() for c in self._componentes)
        if velas_hasta_ahora is None or velas_hasta_ahora.tamanio() < minimo_para_opinar:
            return apoyo.faltan_velas(velas_hasta_ahora, minimo_para_opinar)
        return self._decidir(velas_hasta_ahora)

    def _decidir(self, velas: ListaDoble[Vela]) -> Decision:
        comprar = vender = mantener = 0.0
        for componente in self._componentes:
            decision = componente.estrategia.evaluar(velas)
            voto = componente.peso * decision.confianza
            if decision.senal is Senal.COMPRAR:
                comprar += voto
            elif decision.senal is Senal.VENDER:
                vender += voto
            else:
                mantener += voto
        comprar /= self._suma_pesos
        vender /= self._suma_pesos
        mantener /= self._suma_pesos

        ganadora, confianza = Senal.MANTENER, mantener
        if comprar > mantener and comprar > vender:
            ganadora, confianza, detalle = Senal.COMPRAR, comprar, "gana COMPRAR"
        elif vender > mantener and vender > comprar:
            ganadora, confianza, detalle = Senal.VENDER, vender, "gana VENDER"
        elif comprar == vender and comprar > mantener:
            detalle = "COMPRAR y VENDER empatan, las estrategias se contradicen y se mantiene"
        else:
            detalle = "gana MANTENER"
        motivo = (f"Votación ponderada: COMPRAR {comprar:.2f}, VENDER {vender:.2f}, "
                  f"MANTENER {mantener:.2f}; {detalle}.")
        return apoyo.decidir(velas, ganadora, confianza, motivo)

    def justificacion(self, velas: ListaDoble[Vela], decision: Decision) -> Lista[str]:
        """Frases de las estrategias que votaron lo mismo que la decisión final."""
        frases: Lista[str] = Lista()
        for nombre, componente in self.evaluar_componentes(velas).items():
            if componente.senal is decision.senal:
                frases.agregar(f"{nombre}: {componente.motivo}")
        if frases.esta_vacia():
            frases.agregar(decision.motivo)
        return frases

    def indicadores_actuales(self, velas: ListaDoble[Vela]) -> dict[str, float]:
        valores: dict[str, float] = {}
        for componente in self._componentes:
            valores.update(componente.estrategia.indicadores_actuales(velas))
        return valores
