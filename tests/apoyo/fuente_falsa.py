"""Fuente de mercado en memoria para las pruebas: sin internet, cuenta las consultas y puede fallar."""

import threading

from bitcoinai.estructuras import ListaDoble
from bitcoinai.modelo import Intervalo, Vela

INICIO = 1_700_000_000_000


def generar_velas(cantidad: int, intervalo: Intervalo) -> ListaDoble[Vela]:
    """Velas válidas y consecutivas: la vela i abre en 100 + i, con máximo +5, mínimo -5 y cierre +1."""
    velas: ListaDoble[Vela] = ListaDoble()
    for i in range(cantidad):
        apertura = INICIO + i * intervalo.milisegundos
        precio = 100.0 + i
        velas.agregar_final(Vela(apertura, precio, precio + 5, precio - 5, precio + 1, 10.0,
                                 apertura + intervalo.milisegundos - 1))
    return velas


class FuenteFalsa:
    """Implementa FuenteDeMercado con datos en memoria."""

    def __init__(self, velas: ListaDoble[Vela] | None = None, precio: float = 100.0) -> None:
        """Por defecto, 500 velas diarias sintéticas y precio 100."""
        self.velas = velas if velas is not None else generar_velas(500, Intervalo.D1)
        self.precio = precio
        self.error: Exception | None = None
        self._candado = threading.Lock()
        self._llamadas_velas = 0
        self._llamadas_precio = 0

    def obtener_velas(self, simbolo: str, intervalo: Intervalo, cantidad: int) -> ListaDoble[Vela]:
        """Copia de las últimas ``cantidad`` velas (o el error configurado)."""
        with self._candado:
            self._llamadas_velas += 1
        if self.error is not None:
            raise self.error
        origen = self.velas
        saltar = max(0, origen.tamanio() - cantidad)
        copia: ListaDoble[Vela] = ListaDoble()
        for indice, vela in enumerate(origen):
            if indice >= saltar:
                copia.agregar_final(vela)
        return copia

    def obtener_precio_actual(self, simbolo: str) -> float:
        """El precio configurado (o el error configurado)."""
        with self._candado:
            self._llamadas_precio += 1
        if self.error is not None:
            raise self.error
        return self.precio

    @property
    def llamadas_velas(self) -> int:
        return self._llamadas_velas

    @property
    def llamadas_precio(self) -> int:
        return self._llamadas_precio
