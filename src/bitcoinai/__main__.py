"""Punto de entrada: ``python -m bitcoinai``.

Lee la configuración del entorno, arma la fuente de mercado (Binance con caché)
y arranca el servidor HTTP con uvicorn en 0.0.0.0 y el puerto PORT.
Ctrl+C lo apaga limpiamente.
"""

import logging

import uvicorn
from fastapi import FastAPI

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.mercado import CacheMercado, ClienteBinance


def construir(config: Configuracion) -> FastAPI:
    """Arma la aplicación real: Binance con caché y todos los endpoints."""
    fuente = CacheMercado(ClienteBinance(config.url_base_binance), config.ttl_cache_segundos)
    return crear_app(config, fuente)


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
    uvicorn.run(app, host="0.0.0.0", port=config.puerto, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
