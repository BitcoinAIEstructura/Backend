"""Middlewares ASGI: registro de peticiones, encabezados de seguridad, CORS y captura de errores.

De afuera hacia adentro: registro → seguridad → CORS → errores → FastAPI. Son middlewares
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

    Con un origen concreto (no ``*``) permite credenciales: así el frontend puede
    mandar la cookie de sesión. El navegador nunca acepta credenciales con ``*``.
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
            encabezados["Access-Control-Allow-Credentials"] = "true"
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


RUTAS_DOCUMENTACION = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")
RUTAS_SIN_CACHE = ("/api/cuentas", "/api/sesion")


class MiddlewareSeguridad:
    """Encabezados de seguridad en todas las respuestas.

    - ``X-Content-Type-Options: nosniff``: el navegador no "adivina" tipos de archivo.
    - ``X-Frame-Options: DENY`` y ``frame-ancestors 'none'``: nadie puede meter la API
      en un iframe (evita el *clickjacking*).
    - ``Content-Security-Policy: default-src 'none'``: una respuesta JSON no puede
      cargar ni ejecutar nada. La documentación (/docs) queda fuera, porque necesita
      sus scripts.
    - ``Referrer-Policy: no-referrer`` y ``Permissions-Policy`` sin cámara, micrófono
      ni ubicación.
    - ``Cache-Control: no-store`` en cuentas y sesión: los datos personales no se
      guardan en cachés.
    - ``Strict-Transport-Security`` (solo con HTTPS): el navegador ya no intenta HTTP.
    """

    def __init__(self, app: ASGIApp, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ruta: str = scope["path"]

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                encabezados = MutableHeaders(scope=mensaje)
                encabezados["X-Content-Type-Options"] = "nosniff"
                encabezados["X-Frame-Options"] = "DENY"
                encabezados["Referrer-Policy"] = "no-referrer"
                encabezados["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                encabezados["Cross-Origin-Opener-Policy"] = "same-origin"
                if not ruta.startswith(RUTAS_DOCUMENTACION):
                    encabezados["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                if ruta.startswith(RUTAS_SIN_CACHE):
                    encabezados["Cache-Control"] = "no-store"
                if self.hsts:
                    encabezados["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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
