"""Errores de la API y su conversión a JSON."""

import logging
import math
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException

from bitcoinai.api.respuestas import RespuestaJson, respuesta_error
from bitcoinai.mercado import MercadoError
from bitcoinai.simulacion import OperacionInvalidaError, OrdenNoEncontradaError
from bitcoinai.usuarios.servicio import (
    CodigoInvalidoError,
    CredencialesInvalidasError,
    CuentaError,
    DemasiadosIntentosError,
    DesafioVencidoError,
    OperacionCuentaError,
    RegistroRechazadoError,
    SesionInvalidaError,
)
from bitcoinai.usuarios.validacion import DatoInvalidoError

CODIGOS_CUENTA: tuple[tuple[type[CuentaError], int], ...] = (
    (RegistroRechazadoError, 409),
    (OperacionCuentaError, 409),
    (CredencialesInvalidasError, 401),
    (CodigoInvalidoError, 401),
    (DesafioVencidoError, 401),
    (SesionInvalidaError, 401),
)
"""Código HTTP de cada error de las cuentas (los demás, 400)."""

LOG = logging.getLogger("bitcoinai.api")


class ApiError(Exception):
    """Error que se devuelve al cliente tal cual: código HTTP y mensaje pensado para él.

    Por ejemplo, 400 con el motivo de un parámetro inválido.
    """

    def __init__(self, codigo: int, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


def registrar_manejadores(app: FastAPI) -> None:
    """Convierte las excepciones en respuestas ``{"error": "..."}``.

    - ``ApiError`` → su código y mensaje (400, 404, 409…).
    - ``MercadoError`` → 502 "Fuente de mercado no disponible" (el detalle va solo al registro).
    - ``OrdenNoEncontradaError`` → 404; ``OperacionInvalidaError`` → 409.
    - Cuentas: dato inválido → 400 con ``campo``; correo o documento repetido → 409;
      credenciales, código o sesión inválidos → 401; demasiados intentos → 429 con
      ``Retry-After``.
    - 404 y 405 de FastAPI → mensajes en español; el 405 incluye el encabezado ``Allow``.
    - Validaciones de FastAPI y pydantic (por defecto 422) → 400 con el motivo en español.

    Los errores inesperados (500) los atrapa ``MiddlewareErrores``.
    """

    @app.exception_handler(ApiError)
    async def error_api(peticion: Request, error: ApiError) -> Response:
        return respuesta_error(error.codigo, error.mensaje)

    @app.exception_handler(MercadoError)
    async def error_mercado(peticion: Request, error: MercadoError) -> Response:
        LOG.warning("Fuente de mercado no disponible: %s", error)
        return respuesta_error(502, "Fuente de mercado no disponible")

    @app.exception_handler(HTTPException)
    async def error_http(peticion: Request, error: HTTPException) -> Response:
        ruta = peticion.url.path
        if error.status_code == 404:
            return respuesta_error(404, f"Ruta no encontrada: {ruta}")
        if error.status_code == 405:
            permitidos = (error.headers or {}).get("Allow", "")
            return respuesta_error(405, f"Método {peticion.method} no permitido en {ruta}; use {permitidos}",
                                   {"Allow": permitidos})
        return respuesta_error(error.status_code, str(error.detail))

    @app.exception_handler(OrdenNoEncontradaError)
    async def orden_no_encontrada(peticion: Request, error: OrdenNoEncontradaError) -> Response:
        return respuesta_error(404, str(error))

    @app.exception_handler(OperacionInvalidaError)
    async def operacion_invalida(peticion: Request, error: OperacionInvalidaError) -> Response:
        return respuesta_error(409, str(error))

    @app.exception_handler(DatoInvalidoError)
    async def dato_invalido(peticion: Request, error: DatoInvalidoError) -> Response:
        # "campo" le dice al formulario qué casilla marcar en rojo.
        return RespuestaJson({"error": error.mensaje, "campo": error.campo}, status_code=400)

    @app.exception_handler(DemasiadosIntentosError)
    async def demasiados_intentos(peticion: Request, error: DemasiadosIntentosError) -> Response:
        return respuesta_error(429, error.mensaje, {"Retry-After": str(max(1, math.ceil(error.espera)))})

    @app.exception_handler(CuentaError)
    async def error_cuenta(peticion: Request, error: CuentaError) -> Response:
        codigo = next((c for tipo, c in CODIGOS_CUENTA if isinstance(error, tipo)), 400)
        return respuesta_error(codigo, error.mensaje)

    @app.exception_handler(RequestValidationError)
    async def error_validacion(peticion: Request, error: RequestValidationError) -> Response:
        primero = next(iter(error.errors()), None)
        return respuesta_error(400, traducir_validacion(primero) if primero else "Petición inválida")


def traducir_validacion(error: Mapping[str, Any]) -> str:
    """Convierte un error de validación de FastAPI/pydantic en un mensaje en español."""
    tipo = str(error.get("type", ""))
    loc = tuple(error.get("loc", ()))
    campo = ".".join(str(parte) for parte in loc[1:])
    mensaje = str(error.get("msg", "valor no válido"))
    if tipo == "missing":
        return "Falta el cuerpo JSON de la petición" if not campo else f"Falta el campo '{campo}'"
    if tipo == "json_invalid":
        return f"Cuerpo JSON inválido: {error.get('ctx', {}).get('error', mensaje)}"
    if tipo in ("model_attributes_type", "model_type", "dict_type"):
        return 'El cuerpo debe ser un objeto JSON, por ejemplo {"tipo":"COMPRA","monto":500}'
    if tipo == "value_error":
        return mensaje.removeprefix("Value error, ")
    if tipo in ("int_type", "int_parsing", "int_from_float"):
        return f"El campo '{campo}' debe ser un número entero"
    if tipo in ("float_type", "float_parsing"):
        return f"El campo '{campo}' debe ser un número"
    if tipo in ("bool_type", "bool_parsing"):
        return f"El campo '{campo}' debe ser true o false"
    if tipo == "string_too_long":
        return f"El campo '{campo}' es demasiado largo"
    if tipo == "extra_forbidden":
        return f"Campo no permitido: '{campo}'"
    if tipo == "string_type":
        return f"El campo '{campo}' debe ser un texto"
    return f"Dato inválido en '{campo or 'petición'}': {mensaje}"
