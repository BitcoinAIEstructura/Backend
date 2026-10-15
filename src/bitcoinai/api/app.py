"""Construcción de la aplicación FastAPI."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bitcoinai.alertas.servicio import ServicioAlertas
from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.errores import registrar_manejadores
from bitcoinai.api.middleware import (
    MiddlewareCors,
    MiddlewareErrores,
    MiddlewareLimite,
    MiddlewareRegistro,
    MiddlewareSeguridad,
)
from bitcoinai.api.publicador import Publicador
from bitcoinai.api.respuestas import RespuestaJson
from bitcoinai.api.rutas_alertas import crear_rutas_alertas
from bitcoinai.api.rutas_asistente import crear_rutas_asistente
from bitcoinai.api.rutas_busqueda import crear_rutas_busqueda
from bitcoinai.api.rutas_cuentas import crear_rutas_cuentas
from bitcoinai.api.rutas_estrategia import crear_rutas_estrategia
from bitcoinai.api.rutas_estructuras import crear_rutas_estructuras
from bitcoinai.api.rutas_ia import crear_rutas_ia
from bitcoinai.api.rutas_liga import crear_rutas_liga
from bitcoinai.api.rutas_mercado import crear_rutas_mercado
from bitcoinai.api.rutas_simulacion import crear_rutas_simulacion
from bitcoinai.api.rutas_stream import crear_rutas_stream
from bitcoinai.busqueda import Buscador
from bitcoinai.estructuras import Lista
from bitcoinai.mercado import FuenteDeMercado, PreciosRecientes
from bitcoinai.simulacion import GestorSimulaciones
from bitcoinai.simulacion.ranking import Participante
from bitcoinai.usuarios.servicio import ServicioCuentas


def crear_app(config: Configuracion, fuente: FuenteDeMercado, *, publicador: Publicador | None = None,
              cuentas: ServicioCuentas | None = None, gestor: GestorSimulaciones | None = None,
              participantes: Callable[[float], Lista[Participante]] | None = None,
              alertas: ServicioAlertas | None = None) -> FastAPI:
    """Crea la API con sus dependencias (en las pruebas, una ``FuenteFalsa``).

    - Todas las respuestas son ``application/json; charset=utf-8``, incluidos los errores.
    - Middlewares, de afuera hacia adentro: registro → seguridad → límite → CORS → errores.
    - Los endpoints de la simulación (de cada usuario) se registran si se pasan
      ``cuentas`` y ``gestor`` (también el chat con el bot, ``POST /api/asistente``); al apagar
      el servidor se detienen todos los bots.
    - ``GET /api/stream`` se registra si se pasa un ``publicador``; se inicia al
      arrancar y al apagar cierra las conexiones abiertas.
    - Los endpoints de cuentas y sesión se registran si se pasa ``cuentas``.
    - ``POST /api/estructuras/demo`` siempre; ``GET /api/estructuras`` con ``cuentas`` y ``gestor``.
    - Las alertas de precio (``/api/alertas``) se registran con ``cuentas`` y ``alertas``; su
      vigilante arranca y se detiene con el servidor.
    - ``GET /api/liga`` se registra si se pasan ``cuentas`` y ``participantes`` (quién lee las carteras).
    - La documentación interactiva queda en ``/docs``.
    """

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        if publicador is not None:
            publicador.iniciar()
        if alertas is not None:
            alertas.iniciar()
        yield
        if alertas is not None:
            alertas.detener()
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
    # Los últimos precios (cola circular): los anotan /api/precio y el tiempo real.
    recientes = PreciosRecientes()
    if publicador is not None:
        publicador.usar_recientes(recientes)
    app.include_router(crear_rutas_mercado(fuente, config.simbolo, recientes))
    app.include_router(crear_rutas_estrategia(fuente, config.simbolo))
    app.include_router(crear_rutas_ia(fuente, config.simbolo))
    buscador = Buscador()  # el trie se arma una sola vez
    app.include_router(crear_rutas_busqueda(buscador))
    app.include_router(crear_rutas_estructuras(gestor, cuentas, recientes, buscador, config))
    if gestor is not None and cuentas is not None:
        app.include_router(crear_rutas_simulacion(gestor, cuentas, config))
        app.include_router(crear_rutas_asistente(gestor, cuentas, config))
    if publicador is not None:
        app.include_router(crear_rutas_stream(publicador, cuentas, config))
    if cuentas is not None:
        app.include_router(crear_rutas_cuentas(cuentas, config))
    if cuentas is not None and alertas is not None:
        app.include_router(crear_rutas_alertas(alertas, fuente, config.simbolo, cuentas, config))
    if cuentas is not None and participantes is not None:
        app.include_router(crear_rutas_liga(participantes, fuente, config.simbolo, cuentas, config))
    app.state.publicador, app.state.cuentas, app.state.gestor = publicador, cuentas, gestor

    # El último que se agrega queda más afuera.
    app.add_middleware(MiddlewareErrores)
    app.add_middleware(MiddlewareCors, origen_permitido=config.origen_permitido)
    app.add_middleware(MiddlewareLimite, confiar_proxy=config.confiar_proxy,
                       maximo_general=config.limite_general, maximo_costosas=config.limite_costosas)
    app.add_middleware(MiddlewareSeguridad, hsts=config.cookie_segura)
    app.add_middleware(MiddlewareRegistro)
    return app
