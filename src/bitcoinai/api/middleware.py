"""Middlewares ASGI: registro de peticiones, CORS y captura de errores.

De afuera hacia adentro: registro → CORS → errores → FastAPI. Son middlewares
ASGI "puros" (no ``BaseHTTPMiddleware``) para que funcionen también con
respuestas que quedan abiertas, como el tiempo real de la Fase 7.
"""

import logging
import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from bitcoinai.api.respuestas import respuesta_error

LOG = logging.getLogger("bitcoinai.api")


def normalizar_ruta(ruta: str) -> str:
    """Quita la barra final (salvo en "/"), para que "/health/" sea igual que "/health"."""
    sin_barra = ruta.rstrip("/")
    return sin_barra or "/"


class MiddlewareRegistro:
    """Registra cada petición en una línea: método, ruta, código y milisegundos.

    Es el más externo, así mide el tiempo total. También normaliza la ruta
    (barra final) antes de que FastAPI la busque.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        scope = dict(scope)
        scope["path"] = normalizar_ruta(scope["path"])
        inicio = time.perf_counter()
        codigo = 0

        async def enviar(mensaje: Message) -> None:
            nonlocal codigo
            if mensaje["type"] == "http.response.start":
                codigo = mensaje["status"]
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            milisegundos = round((time.perf_counter() - inicio) * 1000)
            LOG.info("%s %s %s %s ms", scope["method"], scope["path"], codigo, milisegundos)


class MiddlewareCors:
    """Agrega los encabezados CORS a todas las respuestas (también a los errores).

    Contesta directamente las peticiones OPTIONS (preflight) con 204.
    """

    def __init__(self, app: ASGIApp, origen_permitido: str) -> None:
        self.app = app
        self.origen = origen_permitido

    def _poner_encabezados(self, encabezados: MutableHeaders) -> None:
        encabezados["Access-Control-Allow-Origin"] = self.origen
        encabezados["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        encabezados["Access-Control-Allow-Headers"] = "Content-Type"
        encabezados["Access-Control-Max-Age"] = "86400"
        if self.origen != "*":
            encabezados["Vary"] = "Origin"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["method"] == "OPTIONS":
            inicio: Message = {"type": "http.response.start", "status": 204, "headers": []}
            self._poner_encabezados(MutableHeaders(scope=inicio))
            await send(inicio)
            await send({"type": "http.response.body", "body": b""})
            return

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                self._poner_encabezados(MutableHeaders(scope=mensaje))
            await send(mensaje)

        await self.app(scope, receive, enviar)


class MiddlewareErrores:
    """Convierte cualquier error inesperado en 500 ``{"error": "Error interno del servidor"}``.

    La traza completa solo va al registro del servidor, nunca al cliente.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        iniciada = False

        async def enviar(mensaje: Message) -> None:
            nonlocal iniciada
            if mensaje["type"] == "http.response.start":
                iniciada = True
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            LOG.exception("Error no controlado en %s", scope["path"])
            if not iniciada:
                await respuesta_error(500, "Error interno del servidor")(scope, receive, send)
