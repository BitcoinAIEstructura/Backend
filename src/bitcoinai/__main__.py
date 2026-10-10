"""Punto de entrada: ``python -m bitcoinai``.

Lee la configuración del entorno, arma la fuente de mercado (Binance con caché)
y arranca el servidor HTTP con uvicorn en 0.0.0.0 y el puerto PORT.
Ctrl+C lo apaga limpiamente.
"""

import logging

import uvicorn
from fastapi import FastAPI

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.api.publicador import Publicador
from bitcoinai.estrategia import EstrategiaCombinada
from bitcoinai.mercado import CacheMercado, ClienteBinance
from bitcoinai.persistencia import AlmacenArchivos
from bitcoinai.simulacion import BotSimulado, Cartera, LibroDeOrdenes

LOG = logging.getLogger("bitcoinai")


def construir(config: Configuracion) -> FastAPI:
    """Arma la aplicación real: Binance con caché, la simulación y todos los endpoints.

    El bot queda creado pero detenido; se inicia con POST /api/bot/iniciar. La
    simulación se recupera de ``DATA_DIR`` (si hay algo guardado) y se guarda
    después de cada cambio; los cambios se publican en /api/stream.
    """
    fuente = CacheMercado(ClienteBinance(config.url_base_binance), config.ttl_cache_segundos)
    publicador = Publicador(fuente, config.simbolo, config.max_streams)
    libro = LibroDeOrdenes(Cartera(), fuente, config.simbolo)
    if libro.usar_almacen(AlmacenArchivos(config.data_dir)):
        LOG.info("Simulación recuperada de %s", config.data_dir)
    libro.usar_publicador(publicador)
    bot = BotSimulado(libro, fuente, EstrategiaCombinada(), config.simbolo)
    bot.usar_publicador(publicador)
    return crear_app(config, fuente, libro, bot, publicador)


def main() -> None:
    """Arranca el backend."""
    # Registro en una sola línea: "2026-10-09 18:00:00 INFO GET /health 200 1 ms"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # sin una línea por cada petición a Binance
    config = Configuracion.desde_entorno()
    app = construir(config)
    print(f"Backend iniciado en http://0.0.0.0:{config.puerto} "
          f"(símbolo {config.simbolo}, Binance {config.url_base_binance})", flush=True)
    # access_log=False: el registro de cada petición lo hace MiddlewareRegistro.
    # timeout_graceful_shutdown: las conexiones de /api/stream no terminan solas; al apagar se cortan.
    uvicorn.run(app, host="0.0.0.0", port=config.puerto, access_log=False, log_level="warning",
                timeout_graceful_shutdown=3)


if __name__ == "__main__":
    main()
