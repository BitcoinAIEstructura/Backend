"""Interfaz de las fuentes de datos de mercado."""

from typing import Protocol

from bitcoinai.estructuras import ListaDoble
from bitcoinai.modelo import Intervalo, Vela


class FuenteDeMercado(Protocol):
    """Fuente de datos de mercado.

    Permite cambiar Binance por otra fuente (o por una falsa en las pruebas)
    sin tocar el resto del backend. Cualquier clase con estos dos métodos sirve.
    """

    def obtener_velas(self, simbolo: str, intervalo: Intervalo, cantidad: int) -> ListaDoble[Vela]:
        """Obtiene las velas más recientes, de la más antigua a la más reciente.

        Raises:
            MercadoError: si la fuente falla o entrega datos inválidos.
        """
        ...

    def obtener_precio_actual(self, simbolo: str) -> float:
        """Obtiene el último precio negociado del símbolo.

        Raises:
            MercadoError: si la fuente falla o entrega datos inválidos.
        """
        ...
