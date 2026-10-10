"""Estrategia de cruces del MACD con su señal."""

from bitcoinai.estrategia import apoyo
from bitcoinai.estrategia.apoyo import num
from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estrategia.modelo import Decision, Senal
from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import Macd
from bitcoinai.indicadores.incremental import MacdIncremental
from bitcoinai.modelo import Vela


class EstrategiaMacd(Estrategia):
    """Cruces del MACD con su línea de señal (cambio de signo del histograma).

    - COMPRAR cuando el MACD cruza hacia arriba su señal.
    - VENDER cuando la cruza hacia abajo.
    - MANTENER en el resto.

    La confianza crece con el tamaño del histograma relativo al precio.
    Memoria incremental: O(1) por vela nueva.
    """

    def __init__(self, rapido: int = 12, lento: int = 26, senal: int = 9) -> None:
        """Raises: ValueError si los periodos son inválidos."""
        self.macd = Macd(rapido, lento, senal)  # valida los periodos
        super().__init__()

    def nombre(self) -> str:
        return "macd"

    def parametros(self) -> dict[str, object]:
        return self.macd.parametros()

    def velas_minimas(self) -> int:
        """El histograma empieza en la vela lento + señal − 2, y hacen falta dos puntos."""
        return self.macd.lento + self.macd.senal

    def _reiniciar(self) -> None:
        self._calculo = MacdIncremental(self.macd.rapido, self.macd.lento, self.macd.senal)
        self._antes: float | None = None
        self._ahora: float | None = None

    def _agregar(self, vela: Vela) -> None:
        self._calculo.agregar(vela.cierre)
        if self._calculo.histograma is not None:
            self._antes, self._ahora = self._ahora, self._calculo.histograma

    def _decidir(self, velas: ListaDoble[Vela]) -> Decision:
        assert self._antes is not None and self._ahora is not None
        assert self._calculo.macd is not None and self._calculo.senal is not None
        precio = velas.ultimo().cierre
        antes = apoyo.signo(self._antes, precio)
        valor_ahora = self._ahora
        ahora = apoyo.signo(valor_ahora, precio)
        valores = f" (MACD {num(self._calculo.macd)}, señal {num(self._calculo.senal)})"

        if antes <= 0 < ahora:
            return apoyo.decidir(velas, Senal.COMPRAR, apoyo.confianza_por_distancia(valor_ahora / precio),
                                 f"El MACD cruzó por encima de su señal{valores}; el impulso se vuelve alcista.")
        if antes >= 0 > ahora:
            return apoyo.decidir(velas, Senal.VENDER, apoyo.confianza_por_distancia(valor_ahora / precio),
                                 f"El MACD cruzó por debajo de su señal{valores}; el impulso se vuelve bajista.")
        estado = "sigue por encima de" if ahora > 0 else "sigue por debajo de" if ahora < 0 else "está igual que"
        return apoyo.decidir(velas, Senal.MANTENER, apoyo.CONFIANZA_NEUTRA,
                             f"Sin cruce nuevo: el MACD {estado} su señal{valores}.")

    def _valores_actuales(self) -> dict[str, float]:
        valores: dict[str, float] = {}
        if self._calculo.macd is not None:
            valores["macd"] = self._calculo.macd
        if self._calculo.senal is not None:
            valores["senalMacd"] = self._calculo.senal
        if self._calculo.histograma is not None:
            valores["histogramaMacd"] = self._calculo.histograma
        return valores
