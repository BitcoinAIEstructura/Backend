"""Endpoint de tiempo real: GET /api/stream (Server-Sent Events)."""

import asyncio

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.publicador import Publicador, RespuestaStream
from bitcoinai.api.rutas_cuentas import Cookies
from bitcoinai.usuarios.servicio import CuentaError, ServicioCuentas


def crear_rutas_stream(publicador: Publicador, cuentas: ServicioCuentas | None = None,
                       config: Configuracion | None = None) -> APIRouter:
    """Rutas de tiempo real.

    Sin sesión, la conexión recibe solo los eventos públicos (``precio``). Con la
    cookie de sesión recibe además sus propios ``orden``, ``cartera`` y ``senal``.
    """
    rutas = APIRouter()
    cookies = Cookies(config or Configuracion())

    def usuario_de(peticion: Request) -> int | None:
        token = peticion.cookies.get(cookies.sesion)
        if cuentas is None or not token:
            return None
        try:
            usuario, _ = cuentas.sesion_actual(token)
        except CuentaError:
            return None
        return usuario.id

    @rutas.get("/api/stream", response_class=StreamingResponse)
    async def stream(peticion: Request) -> StreamingResponse:
        """Conexión abierta con eventos ``precio`` y, con sesión, ``orden``, ``cartera`` y ``senal``.

        503 si ya hay ``MAX_STREAMS`` conexiones abiertas.
        """
        usuario_id = await run_in_threadpool(usuario_de, peticion)  # la consulta a la base no bloquea el bucle
        return RespuestaStream(publicador, publicador.suscribir(asyncio.get_running_loop(), usuario_id))

    return rutas
