"""Vela (candlestick) de un intervalo de mercado."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vela:
    """Vela de un intervalo: precios de apertura, máximo, mínimo y cierre, y volumen.

    No valida sus datos al crearse, para poder representar lo que llega de la
    fuente tal cual; la validación la hace ``mercado.validar_velas``.

    Atributos:
        tiempo_apertura: momento de apertura, en milisegundos desde 1970 (UTC).
        apertura: precio de apertura.
        maximo: precio máximo del intervalo.
        minimo: precio mínimo del intervalo.
        cierre: precio de cierre.
        volumen: volumen negociado en la moneda base (BTC).
        tiempo_cierre: momento de cierre, en milisegundos desde 1970 (UTC).
    """

    tiempo_apertura: int
    apertura: float
    maximo: float
    minimo: float
    cierre: float
    volumen: float
    tiempo_cierre: int
