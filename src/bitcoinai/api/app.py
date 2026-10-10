"""Construcción de la aplicación FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.errores import registrar_manejadores
from bitcoinai.api.middleware import MiddlewareCors, MiddlewareErrores, MiddlewareRegistro
from bitcoinai.api.respuestas import RespuestaJson
from bitcoinai.api.rutas_estrategia import crear_rutas_estrategia
from bitcoinai.api.rutas_mercado import crear_rutas_mercado
from bitcoinai.api.rutas_simulacion import crear_rutas_simulacion
from bitcoinai.mercado import FuenteDeMercado
from bitcoinai.simulacion import BotSimulado, LibroDeOrdenes


def crear_app(config: Configuracion, fuente: FuenteDeMercado, libro: LibroDeOrdenes | None = None,
              bot: BotSimulado | None = None) -> FastAPI:
    """Crea la API con sus dependencias (en las pruebas, una ``FuenteFalsa``).

    - Todas las respuestas son ``application/json; charset=utf-8``, incluidos los errores.
    - Middlewares, de afuera hacia adentro: registro → CORS → errores.
    - Los endpoints de la simulación se registran si se pasan ``libro`` y ``bot``;
      al apagar el servidor se detiene el bot.
    - La documentación interactiva queda en ``/docs``.
    """

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        yield
        if bot is not None:
            bot.detener()

    app = FastAPI(
        title="Backend del bot de Bitcoin",
        description="Velas de Binance, indicadores, señales y simulación de operaciones. "
                    "No opera con dinero real.",
        version="2.0.0",
        default_response_class=RespuestaJson,
        redirect_slashes=False,  # la barra final la quita MiddlewareRegistro, sin redirigir
        lifespan=ciclo_de_vida,
    )
    registrar_manejadores(app)
    app.include_router(crear_rutas_mercado(fuente, config.simbolo))
    app.include_router(crear_rutas_estrategia(fuente, config.simbolo))
    if libro is not None and bot is not None:
        app.include_router(crear_rutas_simulacion(libro, bot))

    # El último que se agrega queda más afuera.
    app.add_middleware(MiddlewareErrores)
    app.add_middleware(MiddlewareCors, origen_permitido=config.origen_permitido)
    app.add_middleware(MiddlewareRegistro)
    return app
