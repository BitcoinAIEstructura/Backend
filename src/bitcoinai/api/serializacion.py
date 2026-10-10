"""Conversión del dominio al JSON del contrato (borde de la API).

El contrato usa nombres en camelCase (``tiempoApertura``), como la versión
Java. Aquí, y solo aquí, las estructuras propias se convierten a ``list``
para que FastAPI escriba el JSON.
"""

from typing import Any

from bitcoinai.estructuras import ListaDoble
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
