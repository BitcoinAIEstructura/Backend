"""MACD (Moving Average Convergence Divergence)."""

from dataclasses import dataclass

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import series
from bitcoinai.indicadores.base import Indicador, Serie
from bitcoinai.modelo import Vela


@dataclass(frozen=True, slots=True)
class ResultadoMacd:
    """Las tres series del MACD.

    La señal y el histograma empiezan más tarde que la línea MACD (necesitan su
    propio calentamiento), así que tienen menos puntos.

    Atributos:
        macd: EMA rápida − EMA lenta.
        senal: EMA de la línea MACD.
        histograma: macd − señal.
    """

    macd: Serie
    senal: Serie
    histograma: Serie


class Macd(Indicador):
    """MACD.

    Fórmula:
        - línea MACD = EMA(rápida) − EMA(lenta) de los cierres;
        - señal = EMA(señal) de la línea MACD;
        - histograma = MACD − señal.

    Valores habituales: 12, 26 y 9. La línea MACD empieza en la vela lenta − 1 y
    la señal ``señal − 1`` puntos después.
    Complejidad: O(n). Tres EMA (O(n) cada una) y dos restas alineadas (O(n)).
    """

    def __init__(self, rapido: int = 12, lento: int = 26, senal: int = 9) -> None:
        """Raises: ValueError si algún periodo es menor que 1 o lento <= rápido."""
        if rapido < 1 or senal < 1:
            raise ValueError("Los periodos del MACD deben ser al menos 1")
        if lento <= rapido:
            raise ValueError("El periodo lento del MACD debe ser mayor que el rápido")
        self.rapido = rapido
        self.lento = lento
        self.senal = senal

    def nombre(self) -> str:
        return "macd"

    def parametros(self) -> dict[str, object]:
        return {"rapido": self.rapido, "lento": self.lento, "senal": self.senal}

    def calcular_completo(self, velas: ListaDoble[Vela] | None) -> ResultadoMacd:
        """Las tres series. Complejidad: O(n)."""
        cierres = series.cierres(velas)
        ema_lenta = series.ema(cierres, self.lento)

        # La EMA rápida empieza (lento − rápido) velas antes que la lenta. Para
        # alinearlas solo sirven sus valores más recientes, tantos como tenga la
        # lenta: series.ultimos los toma recorriendo hacia atrás desde la cola.
        ema_rapida = series.ultimos(series.ema(cierres, self.rapido), ema_lenta.tamanio())
        linea_macd = series.restar(ema_rapida, ema_lenta)

        linea_senal = series.ema(linea_macd, self.senal)
        # Igual para el histograma: los últimos valores del MACD, tantos como la señal.
        histograma = series.restar(series.ultimos(linea_macd, linea_senal.tamanio()), linea_senal)
        return ResultadoMacd(linea_macd, linea_senal, histograma)

    def calcular(self, velas: ListaDoble[Vela] | None) -> Serie:
        """La serie principal es la línea MACD. Complejidad: O(n)."""
        return self.calcular_completo(velas).macd

    def calcular_series(self, velas: ListaDoble[Vela]) -> dict[str, Serie]:
        """``macd``, ``senal`` e ``histograma``. Complejidad: O(n)."""
        resultado = self.calcular_completo(velas)
        return {"macd": resultado.macd, "senal": resultado.senal, "histograma": resultado.histograma}
