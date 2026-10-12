"""GET /api/buscar?q=…: la búsqueda de Ctrl + K (páginas, acciones, indicadores y conceptos).

Es pública: el catálogo no tiene nada privado. El trie se arma una sola vez al crear la app.
"""

from typing import Any

from fastapi import APIRouter

from bitcoinai.api.errores import ApiError
from bitcoinai.busqueda import Buscador
from bitcoinai.busqueda.buscador import LARGO_MAXIMO_CONSULTA, LIMITE_POR_DEFECTO

LIMITE_MAXIMO = 20


def crear_rutas_busqueda(buscador: Buscador | None = None) -> APIRouter:
    rutas = APIRouter()
    elegido = buscador or Buscador()

    @rutas.get("/api/buscar")
    def buscar(q: str = "", limite: str = "") -> dict[str, Any]:
        """Entradas cuyas palabras empiezan como las de ``q`` (todas deben coincidir)."""
        if len(q) > LARGO_MAXIMO_CONSULTA:
            raise ApiError(400, f"La búsqueda es demasiado larga (máximo {LARGO_MAXIMO_CONSULTA} caracteres)")
        try:
            cuantos = int(limite) if limite.strip() else LIMITE_POR_DEFECTO
        except ValueError:
            cuantos = 0
        if not 1 <= cuantos <= LIMITE_MAXIMO:
            raise ApiError(400, f"Parámetro 'limite' inválido: '{limite}'. "
                                f"Debe ser un entero entre 1 y {LIMITE_MAXIMO}")
        return {
            "consulta": q,
            "resultados": [
                {"id": e.id, "titulo": e.titulo, "descripcion": e.descripcion, "ruta": e.ruta, "tipo": e.tipo}
                for e in elegido.buscar(q, cuantos)
            ],
            "palabrasIndexadas": elegido.palabras_indexadas(),
            "nodosTrie": elegido.nodos_del_trie(),
        }

    return rutas
