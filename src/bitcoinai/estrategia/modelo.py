"""Señales, direcciones y decisiones."""

import math
from dataclasses import dataclass
from enum import Enum


class Senal(Enum):
    """Lo que una estrategia recomienda hacer."""

    COMPRAR = "COMPRAR"
    """Abrir una posición larga (comprar BTC)."""
    VENDER = "VENDER"
    """Cerrar la posición (vender el BTC)."""
    MANTENER = "MANTENER"
    """No hacer nada."""


class Direccion(Enum):
    """Dirección esperada del precio según el pronóstico."""

    SUBE = "SUBE"
    BAJA = "BAJA"
    LATERAL = "LATERAL"


@dataclass(frozen=True, slots=True)
class Decision:
    """Decisión de una estrategia en una vela.

    Atributos:
        tiempo: tiempo de apertura de la vela en que se decidió.
        senal: qué hacer.
        precio: cierre de esa vela.
        confianza: entre 0 y 1.
        motivo: una frase en español que explica por qué.
    """

    tiempo: int
    senal: Senal
    precio: float
    confianza: float
    motivo: str

    def __post_init__(self) -> None:
        """Raises: ValueError si la confianza no está entre 0 y 1 o el motivo está vacío."""
        if not self.motivo or not self.motivo.strip():
            raise ValueError("La decisión necesita un motivo")
        if math.isnan(self.confianza) or not 0 <= self.confianza <= 1:
            raise ValueError(f"La confianza debe estar entre 0 y 1: {self.confianza}")
