"""Intervalos de vela soportados."""

from __future__ import annotations

from enum import Enum


class Intervalo(Enum):
    """Intervalo de vela, con el código que usa Binance y su duración en milisegundos."""

    M1 = ("1m", 60_000)
    M5 = ("5m", 5 * 60_000)
    M15 = ("15m", 15 * 60_000)
    H1 = ("1h", 60 * 60_000)
    H4 = ("4h", 4 * 60 * 60_000)
    D1 = ("1d", 24 * 60 * 60_000)

    def __init__(self, codigo: str, milisegundos: int) -> None:
        self.codigo = codigo
        """Código que usa Binance, por ejemplo ``"1d"``."""
        self.milisegundos = milisegundos
        """Duración del intervalo en milisegundos."""

    @classmethod
    def desde_codigo(cls, codigo: str) -> Intervalo:
        """Busca el intervalo de un código de Binance como ``"1m"``, ``"4h"`` o ``"1d"``.

        Complejidad: O(k), con k = 6 intervalos.

        Raises:
            ValueError: si el código no está soportado.
        """
        for intervalo in cls:
            if intervalo.codigo == codigo:
                return intervalo
        raise ValueError(f"Intervalo no soportado: {codigo}. Use 1m, 5m, 15m, 1h, 4h o 1d")
