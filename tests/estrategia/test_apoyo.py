"""Pruebas de las utilidades que comparten las estrategias.

``agregar_ultimo`` es la que arma el diccionario de valores que se publica con cada
decisión: si una serie todavía no tiene puntos (calentamiento), su clave no debe
aparecer, para que el frontend no reciba un valor inventado.
"""

from bitcoinai.estructuras import ListaDoble
from bitcoinai.estrategia import apoyo
from bitcoinai.indicadores.base import PuntoIndicador


def serie_de(*valores: float) -> ListaDoble[PuntoIndicador]:
    serie: ListaDoble[PuntoIndicador] = ListaDoble()
    for indice, valor in enumerate(valores):
        serie.agregar_final(PuntoIndicador(indice * 60_000, valor))
    return serie


def test_agregar_ultimo_toma_el_ultimo_punto() -> None:
    valores: dict[str, float] = {}
    apoyo.agregar_ultimo(valores, "rsi", serie_de(10.0, 55.5, 70.25))
    assert valores == {"rsi": 70.25}


def test_una_serie_vacia_no_agrega_la_clave() -> None:
    valores: dict[str, float] = {"rsi": 55.5}
    apoyo.agregar_ultimo(valores, "macd", serie_de())
    assert valores == {"rsi": 55.5}


def test_varias_series_se_acumulan() -> None:
    valores: dict[str, float] = {}
    apoyo.agregar_ultimo(valores, "rsi", serie_de(30.0))
    apoyo.agregar_ultimo(valores, "macd", serie_de())
    apoyo.agregar_ultimo(valores, "volatilidad", serie_de(0.02))
    assert valores == {"rsi": 30.0, "volatilidad": 0.02}
