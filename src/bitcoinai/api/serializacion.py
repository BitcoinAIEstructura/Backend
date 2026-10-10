"""Conversión del dominio al JSON del contrato (borde de la API).

El contrato usa nombres en camelCase (``tiempoApertura``), como la versión
Java. Aquí, y solo aquí, las estructuras propias se convierten a ``list``
para que FastAPI escriba el JSON.
"""

from typing import Any

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import PuntoIndicador, ResultadoCaida, Serie
from bitcoinai.modelo import Vela


def vela_a_json(vela: Vela) -> dict[str, Any]:
    """Una vela con los nombres del contrato. Complejidad: O(1)."""
    return {
        "tiempoApertura": vela.tiempo_apertura,
        "apertura": vela.apertura,
        "maximo": vela.maximo,
        "minimo": vela.minimo,
        "cierre": vela.cierre,
        "volumen": vela.volumen,
        "tiempoCierre": vela.tiempo_cierre,
    }


def velas_a_json(velas: ListaDoble[Vela]) -> list[dict[str, Any]]:
    """Las velas en orden, como arreglo JSON. Complejidad: O(n)."""
    return [vela_a_json(vela) for vela in velas]


def punto_a_json(punto: PuntoIndicador) -> dict[str, Any]:
    """Un punto de indicador: ``{"tiempo", "valor"}``. Complejidad: O(1)."""
    return {"tiempo": punto.tiempo, "valor": punto.valor}


def serie_a_json(serie: Serie) -> list[dict[str, Any]]:
    """Una serie de puntos como arreglo JSON. Complejidad: O(n)."""
    return [punto_a_json(punto) for punto in serie]


def series_a_json(series: dict[str, Serie]) -> dict[str, Any]:
    """Series con nombre, por ejemplo ``{"macd": [...], "senal": [...]}``. Complejidad: O(n)."""
    return {nombre: serie_a_json(serie) for nombre, serie in series.items()}


def caida_a_json(caida: ResultadoCaida) -> dict[str, Any]:
    """Máxima caída con los nombres del contrato. Complejidad: O(1)."""
    return {
        "caidaMaxima": caida.caida_maxima,
        "tiempoPico": caida.tiempo_pico,
        "valorPico": caida.valor_pico,
        "tiempoValle": caida.tiempo_valle,
        "valorValle": caida.valor_valle,
    }
