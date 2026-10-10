"""Construcción de la aplicación FastAPI."""

from fastapi import FastAPI

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.errores import registrar_manejadores
from bitcoinai.api.middleware import MiddlewareCors, MiddlewareErrores, MiddlewareRegistro
from bitcoinai.api.respuestas import RespuestaJson
from bitcoinai.api.rutas_mercado import crear_rutas_mercado
from bitcoinai.mercado import FuenteDeMercado


def crear_app(config: Configuracion, fuente: FuenteDeMercado) -> FastAPI:
    """Crea la API con sus dependencias (en las pruebas, una ``FuenteFalsa``).

    - Todas las respuestas son ``application/json; charset=utf-8``, incluidos los errores.
    - Middlewares, de afuera hacia adentro: registro → CORS → errores.
    - La documentación interactiva queda en ``/docs``.
    """

    app = FastAPI(
        title="Backend del bot de Bitcoin",
        description="Velas de Binance, indicadores, señales y simulación de operaciones. "
                    "No opera con dinero real.",
        version="2.0.0",
        default_response_class=RespuestaJson,
        redirect_slashes=False,  # la barra final la quita MiddlewareRegistro, sin redirigir
    )
    registrar_manejadores(app)
    app.include_router(crear_rutas_mercado(fuente, config.simbolo))

    # El último que se agrega queda más afuera.
    app.add_middleware(MiddlewareErrores)
    app.add_middleware(MiddlewareCors, origen_permitido=config.origen_permitido)
    app.add_middleware(MiddlewareRegistro)
    return app
