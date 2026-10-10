"""Estrategia de cruce de medias móviles."""

from bitcoinai.estrategia import apoyo
from bitcoinai.estrategia.apoyo import num
from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estrategia.modelo import Decision, Senal
from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores.incremental import SmaIncremental
from bitcoinai.modelo import Vela


class CruceDeMedias(Estrategia):
    """Cruce de medias móviles simples.

    - COMPRAR en la vela en que la SMA corta cruza hacia arriba la larga.
    - VENDER en la vela en que la cruza hacia abajo.
    - MANTENER en el resto.

    La confianza crece con la separación entre las medias tras el cruce. Solo
    interesan los dos valores más recientes de cada media (antes y ahora), que se
    mantienen con memoria incremental: O(1) por vela nueva.
    """

    def __init__(self, corta: int = 20, larga: int = 50) -> None:
        """Raises: ValueError si no se cumple 1 <= corta < larga."""
        if corta < 1 or larga <= corta:
            raise ValueError(f"Se necesita 1 <= corta < larga; recibido corta={corta}, larga={larga}")
        self.corta = corta
        self.larga = larga
        super().__init__()

    def nombre(self) -> str:
        return "cruce"

    def parametros(self) -> dict[str, object]:
        return {"corta": self.corta, "larga": self.larga}

    def velas_minimas(self) -> int:
        """Hacen falta dos puntos de la media larga para detectar un cruce."""
        return self.larga + 1

    def _reiniciar(self) -> None:
        self._sma_corta = SmaIncremental(self.corta)
        self._sma_larga = SmaIncremental(self.larga)
        self._antes: tuple[float, float] | None = None
        self._ahora: tuple[float, float] | None = None

    def _agregar(self, vela: Vela) -> None:
        corta = self._sma_corta.agregar(vela.cierre)
        larga = self._sma_larga.agregar(vela.cierre)
        if corta is not None and larga is not None:
            self._antes, self._ahora = self._ahora, (corta, larga)

    def _decidir(self, velas: ListaDoble[Vela]) -> Decision:
        assert self._antes is not None and self._ahora is not None
        corta, larga = self._ahora
        precio = velas.ultimo().cierre
        antes = apoyo.signo(self._antes[0] - self._antes[1], precio)
        diferencia = corta - larga
        ahora = apoyo.signo(diferencia, precio)

        def medias(verbo: str) -> str:
            return f"la SMA {self.corta} ({num(corta)}) {verbo} la SMA {self.larga} ({num(larga)})"

        confianza = apoyo.confianza_por_distancia(diferencia / precio)
        if antes <= 0 < ahora:
            return apoyo.decidir(velas, Senal.COMPRAR, confianza, f"Cruce alcista: {medias('cruzó por encima de')}; "
                                                                  "posible inicio de tendencia alcista.")
        if antes >= 0 > ahora:
            return apoyo.decidir(velas, Senal.VENDER, confianza, f"Cruce bajista: {medias('cruzó por debajo de')}; "
                                                                 "posible inicio de tendencia bajista.")
        estado = "sigue por encima de" if ahora > 0 else "sigue por debajo de" if ahora < 0 else "está igual que"
        return apoyo.decidir(velas, Senal.MANTENER, apoyo.CONFIANZA_NEUTRA, f"Sin cruce nuevo: {medias(estado)}.")

    def _valores_actuales(self) -> dict[str, float]:
        valores: dict[str, float] = {}
        if self._sma_corta.valor is not None:
            valores["smaCorta"] = self._sma_corta.valor
        if self._sma_larga.valor is not None:
            valores["smaLarga"] = self._sma_larga.valor
        return valores
