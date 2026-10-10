"""Punto de un indicador y clase base de los indicadores."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from bitcoinai.estructuras import ListaDoble
from bitcoinai.modelo import Vela


@dataclass(frozen=True, slots=True)
class PuntoIndicador:
    """Un valor de un indicador en un momento dado.

    Atributos:
        tiempo: tiempo de apertura de la vela a la que corresponde (ms desde 1970, UTC).
        valor: valor del indicador.
    """

    tiempo: int
    valor: float


Serie = ListaDoble[PuntoIndicador]
"""Serie de puntos de un indicador, en orden cronológico."""


class Indicador(ABC):
    """Indicador técnico calculado sobre los precios de cierre de una serie de velas.

    Las primeras velas, mientras no hay datos suficientes (periodo de
    calentamiento), no generan punto. Si hay menos velas que las necesarias, el
    resultado es una serie vacía, nunca un error.
    """

    @abstractmethod
    def nombre(self) -> str:
        """Nombre corto, por ejemplo ``"rsi"``."""

    @abstractmethod
    def parametros(self) -> dict[str, object]:
        """Parámetros con que se creó, por ejemplo ``{"periodo": 14}``."""

    @abstractmethod
    def calcular(self, velas: ListaDoble[Vela]) -> Serie:
        """Serie principal del indicador: un punto por vela después del calentamiento."""

    def calcular_series(self, velas: ListaDoble[Vela]) -> dict[str, Serie]:
        """Todas las series con su nombre. Por defecto solo la principal, como ``"valor"``.

        MACD y Bollinger devuelven tres series.
        """
        return {"valor": self.calcular(velas)}
