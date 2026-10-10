"""Construcción de la aplicación FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.errores import registrar_manejadores
from bitcoinai.api.middleware import MiddlewareCors, MiddlewareErrores, MiddlewareRegistro, MiddlewareSeguridad
from bitcoinai.api.publicador import Publicador
from bitcoinai.api.respuestas import RespuestaJson
from bitcoinai.api.rutas_cuentas import crear_rutas_cuentas
from bitcoinai.api.rutas_estrategia import crear_rutas_estrategia
from bitcoinai.api.rutas_mercado import crear_rutas_mercado
from bitcoinai.api.rutas_simulacion import crear_rutas_simulacion
from bitcoinai.api.rutas_stream import crear_rutas_stream
from bitcoinai.mercado import FuenteDeMercado
from bitcoinai.simulacion import GestorSimulaciones
from bitcoinai.usuarios.servicio import ServicioCuentas


def crear_app(config: Configuracion, fuente: FuenteDeMercado, *, publicador: Publicador | None = None,
              cuentas: ServicioCuentas | None = None, gestor: GestorSimulaciones | None = None) -> FastAPI:
    """Crea la API con sus dependencias (en las pruebas, una ``FuenteFalsa``).

    - Todas las respuestas son ``application/json; charset=utf-8``, incluidos los errores.
    - Middlewares, de afuera hacia adentro: registro → seguridad → CORS → errores.
    - Los endpoints de la simulación (de cada usuario) se registran si se pasan
      ``cuentas`` y ``gestor``; al apagar el servidor se detienen todos los bots.
    - ``GET /api/stream`` se registra si se pasa un ``publicador``; se inicia al
      arrancar y al apagar cierra las conexiones abiertas.
    - Los endpoints de cuentas y sesión se registran si se pasa ``cuentas``.
    - La documentación interactiva queda en ``/docs``.
    """

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        if publicador is not None:
            publicador.iniciar()
        yield
        if gestor is not None:
            gestor.detener_todos()
        if publicador is not None:
            publicador.detener()

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
    if gestor is not None and cuentas is not None:
        app.include_router(crear_rutas_simulacion(gestor, cuentas, config))
    if publicador is not None:
        app.include_router(crear_rutas_stream(publicador, cuentas, config))
    if cuentas is not None:
        app.include_router(crear_rutas_cuentas(cuentas, config))
    app.state.publicador, app.state.cuentas, app.state.gestor = publicador, cuentas, gestor

    # El último que se agrega queda más afuera.
    app.add_middleware(MiddlewareErrores)
    app.add_middleware(MiddlewareCors, origen_permitido=config.origen_permitido)
    app.add_middleware(MiddlewareSeguridad, hsts=config.cookie_segura)
    app.add_middleware(MiddlewareRegistro)
    return app
