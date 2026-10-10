"""Pronóstico simple derivado de una decisión."""

from dataclasses import dataclass

from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estrategia.modelo import Decision, Direccion, Senal
from bitcoinai.estructuras import Lista, ListaDoble
from bitcoinai.modelo import Vela

AVISO = "Resultado de pruebas con datos históricos; no es asesoría financiera ni garantiza ganancias"
"""Aviso fijo que acompaña todo pronóstico y todo backtest."""


@dataclass(frozen=True, slots=True)
class Pronostico:
    """Pronóstico simple derivado de la decisión de una estrategia (normalmente la combinada).

    COMPRAR → SUBE, VENDER → BAJA, MANTENER → LATERAL, con la misma confianza.
    Incluye las frases que lo justifican y el valor actual de los indicadores.

    **Aviso: Resultado de pruebas con datos históricos; no es asesoría financiera
    ni garantiza ganancias.**
    """

    direccion: Direccion
    confianza: float
    justificacion: Lista[str]
    indicadores: dict[str, float]
    aviso: str = AVISO

    @classmethod
    def desde(cls, estrategia: Estrategia, velas: ListaDoble[Vela], decision: Decision) -> "Pronostico":
        """Arma el pronóstico de una decisión ya tomada con esas velas."""
        return cls(direccion_de(decision.senal), decision.confianza,
                   estrategia.justificacion(velas, decision), estrategia.indicadores_actuales(velas))


def direccion_de(senal: Senal) -> Direccion:
    """Traduce una señal a dirección esperada."""
    if senal is Senal.COMPRAR:
        return Direccion.SUBE
    if senal is Senal.VENDER:
        return Direccion.BAJA
    return Direccion.LATERAL
