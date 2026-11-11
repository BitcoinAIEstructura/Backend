"""Punto de entrada: ``python -m bitcoinai``.

Lee la configuración del entorno, arma la fuente de mercado (Binance con caché)
y arranca el servidor HTTP con uvicorn en 0.0.0.0 y el puerto PORT.
Ctrl+C lo apaga limpiamente.

Responsabilidades principales:

- Cargar variables desde ``.env`` sin pisar las del entorno del sistema.
- Abrir SQLite y aplicar las migraciones pendientes.
- Construir la app FastAPI con cuentas, simulación, alertas y datos externos.
- Arrancar uvicorn con el registro de peticiones propio del middleware.
"""

import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from bitcoinai.alertas.servicio import ServicioAlertas
from bitcoinai.api import Configuracion, crear_app
from bitcoinai.api.publicador import Publicador, PublicadorDeUsuario
from bitcoinai.api.rutas_alertas import alerta_a_json
from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.externos import DatosExternos
from bitcoinai.ia.piloto import PilotoIA
from bitcoinai.ia.servicio import ServicioIA
from bitcoinai.mercado import CacheMercado, ClienteBinance
from bitcoinai.notificaciones import EnviadorCorreo, enviador_desde_entorno
from bitcoinai.persistencia import AlmacenBaseDatos, participantes_activos
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.seguridad.claves import cargar_clave
from bitcoinai.seguridad.contrasenas import HashContrasenas
from bitcoinai.simulacion import GestorSimulaciones
from bitcoinai.usuarios.servicio import ServicioCuentas

LOG = logging.getLogger("bitcoinai")


def abrir_base_datos(config: Configuracion) -> BaseDatos:
    """La base SQLite con las migraciones al día."""
    bd = BaseDatos(config.ruta_base_datos)
    aplicadas = migrar(bd)
    if aplicadas:
        LOG.info("Base de datos %s: %d migraciones aplicadas", config.ruta_base_datos, aplicadas)
    return bd


def cargar_env(archivo: str = ".env") -> int:
    """Lee ``NOMBRE=valor`` de un archivo .env (si existe) sin pisar lo que ya esté en el entorno.

    Así la contraseña de aplicación de Gmail puede quedar en ``.env`` (que no se sube a git)
    en vez de escribirse en cada terminal. Devuelve cuántas variables cargó.
    """
    ruta = Path(archivo)
    if not ruta.is_file():
        return 0
    cargadas = 0
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        nombre, _, valor = linea.partition("=")
        nombre, valor = nombre.strip(), valor.strip().strip('"').strip("'")
        if nombre and nombre not in os.environ:
            os.environ[nombre] = valor
            cargadas += 1
    return cargadas


def construir_cuentas(config: Configuracion, bd: BaseDatos, hasher: HashContrasenas | None = None,
                      correo: EnviadorCorreo | None = None) -> ServicioCuentas:
    """Servicio de cuentas con la clave de cifrado y el envío de correos; limpia las sesiones vencidas.

    Las cuentas nuevas siempre confirman su correo: por SMTP si está configurado (``SMTP_USUARIO``
    y ``SMTP_CONTRASENA``) o, sin eso, guardando los correos en ``<DATA_DIR>/correos``.
    """
    enviador = correo or enviador_desde_entorno(config.data_dir)
    LOG.info("Correos: %s", enviador.descripcion())
    cuentas = ServicioCuentas(bd, Cifrador(cargar_clave(config.data_dir)), hasher or HashContrasenas(),
                              correo=enviador)
    cuentas.sesiones.limpiar_vencidos()
    return cuentas


def construir(config: Configuracion, hasher: HashContrasenas | None = None) -> FastAPI:
    """Arma la aplicación real: Binance con caché, cuentas, la simulación de cada usuario y todos los endpoints.

    La simulación de cada usuario se carga de la base la primera vez que la usa y
    se guarda después de cada cambio; sus eventos le llegan solo a él por /api/stream.
    Los bots quedan detenidos; cada usuario enciende el suyo con POST /api/bot/iniciar.
    """
    fuente = CacheMercado(ClienteBinance(config.url_base_binance), config.ttl_cache_segundos)
    publicador = Publicador(fuente, config.simbolo, config.max_streams)
    bd = abrir_base_datos(config)
    externos = DatosExternos()
    # Una sola IA: la usan la página de predicciones, el consejo y el piloto de todos los bots.
    ia = ServicioIA(fuente, config.simbolo, externos=externos)
    gestor = GestorSimulaciones(fuente, config.simbolo,
                                crear_almacen=lambda usuario: AlmacenBaseDatos(bd, usuario),
                                crear_publicador=lambda usuario: PublicadorDeUsuario(publicador, usuario),
                                maximo_bots=config.max_bots, piloto=PilotoIA(ia, fuente, config.simbolo))
    # Cuando se cumple una alerta, le llega solo a su dueño por /api/stream.
    alertas = ServicioAlertas(bd, fuente, config.simbolo,
                              al_disparar=lambda a: publicador.publicar_a(a.usuario_id, "alerta", alerta_a_json(a)))
    return crear_app(config, fuente, publicador=publicador, cuentas=construir_cuentas(config, bd, hasher),
                     gestor=gestor, participantes=lambda precio: participantes_activos(bd, precio), alertas=alertas,
                     externos=externos, ia=ia)


def main() -> None:
    """Arranca el backend."""
    # Registro en una sola línea: "2026-10-09 18:00:00 INFO GET /health 200 1 ms"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # sin una línea por cada petición a Binance
    if cargadas := cargar_env():
        LOG.info("Variables leídas de .env: %d", cargadas)
    config = Configuracion.desde_entorno()
    app = construir(config)
    LOG.info("Backend iniciado en http://0.0.0.0:%s (símbolo %s, Binance %s)",
             config.puerto, config.simbolo, config.url_base_binance)
    # access_log=False: el registro de cada petición lo hace MiddlewareRegistro.
    # timeout_graceful_shutdown: las conexiones de /api/stream no terminan solas; al apagar se cortan.
    uvicorn.run(app, host="0.0.0.0", port=config.puerto, access_log=False, log_level="warning",
                timeout_graceful_shutdown=3)


if __name__ == "__main__":
    main()
