"""Endpoint de tiempo real: GET /api/stream (Server-Sent Events)."""

import asyncio

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from bitcoinai.api.publicador import Publicador, RespuestaStream


def crear_rutas_stream(publicador: Publicador) -> APIRouter:
    """Rutas de tiempo real con el publicador dado."""
    rutas = APIRouter()

    @rutas.get("/api/stream", response_class=StreamingResponse)
    async def stream() -> StreamingResponse:
        """Conexión abierta con eventos ``precio``, ``orden``, ``cartera`` y ``senal``.

        503 si ya hay ``MAX_STREAMS`` conexiones abiertas.
        """
        return RespuestaStream(publicador, publicador.suscribir(asyncio.get_running_loop()))

    return rutas
