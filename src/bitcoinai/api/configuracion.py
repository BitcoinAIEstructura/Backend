"""Configuración del backend leída de variables de entorno."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from bitcoinai.mercado import URL_BASE_POR_DEFECTO

_SIMBOLO_VALIDO = re.compile(r"[A-Z0-9]{2,20}")


@dataclass(frozen=True, slots=True)
class Configuracion:
    """Configuración del backend.

    El único secreto (``CLAVE_CIFRADO``) no se guarda aquí: lo lee
    ``seguridad.claves`` directamente, para que nunca aparezca en registros.

    Atributos:
        puerto: puerto HTTP (``PORT``, por defecto 8080; Railway lo inyecta).
        url_base_binance: URL base de Binance (``BINANCE_BASE_URL``).
        origen_permitido: origen permitido para CORS (``ORIGEN_PERMITIDO``, por defecto ``*``).
        ttl_cache_segundos: segundos de caché de los datos de mercado (``TTL_CACHE_SEGUNDOS``, por defecto 30).
        simbolo: par de mercado (``SIMBOLO``, por defecto BTCUSDT).
        max_streams: conexiones simultáneas a /api/stream (``MAX_STREAMS``, por defecto 50).
        max_bots: bots simulados encendidos a la vez entre todos los usuarios (``MAX_BOTS``, por defecto 20).
        data_dir: carpeta donde se guarda la simulación (``DATA_DIR``, por defecto ``./data``).
        base_datos: archivo SQLite de usuarios y sesiones (``BASE_DATOS``, por defecto
            ``<DATA_DIR>/bitcoinai.db``).
        cookie_segura: si la cookie de sesión lleva ``Secure`` (``COOKIE_SEGURA``; ponla en
            ``true`` cuando haya HTTPS, como en Railway).
        confiar_proxy: si se cree el encabezado ``X-Forwarded-For`` para saber la IP real
            (``CONFIAR_PROXY``; solo detrás de un proxy propio, como Railway o el frontend).
        limite_general: peticiones a ``/api`` por minuto y por IP (``LIMITE_GENERAL``, 600).
        limite_costosas: peticiones por minuto y por IP a las rutas costosas, como la IA
            (``LIMITE_COSTOSAS``, 30).
    """

    # Servidor y despliegue.
    puerto: int = 8080
    url_base_binance: str = URL_BASE_POR_DEFECTO

    # CORS: origen del frontend autorizado a llamar la API ("*" en desarrollo).
    origen_permitido: str = "*"

    # Mercado y almacenamiento.
    ttl_cache_segundos: int = 30
    simbolo: str = "BTCUSDT"
    max_streams: int = 50
    max_bots: int = 20
    data_dir: str = "./data"
    base_datos: str = ""

    # Seguridad de la sesión y del proxy.
    cookie_segura: bool = False
    confiar_proxy: bool = False

    # Límites de peticiones por minuto y por IP.
    limite_general: int = 600
    limite_costosas: int = 30

    @property
    def ruta_base_datos(self) -> str:
        return self.base_datos or f"{self.data_dir.rstrip('/')}/bitcoinai.db"

    @classmethod
    def desde_entorno(cls, entorno: Mapping[str, str] | None = None) -> Configuracion:
        """Lee la configuración de las variables de entorno (o de un dict, en las pruebas).

        Raises:
            ValueError: con un mensaje claro si alguna variable tiene un valor inválido.
        """
        variables = os.environ if entorno is None else entorno
        simbolo = _texto(variables, "SIMBOLO", "BTCUSDT").upper()
        if not _SIMBOLO_VALIDO.fullmatch(simbolo):
            raise ValueError(f"SIMBOLO inválido: {simbolo}")
        return cls(
            puerto=_entero(variables, "PORT", 8080, 0, 65_535),
            url_base_binance=_texto(variables, "BINANCE_BASE_URL", URL_BASE_POR_DEFECTO),
            origen_permitido=_texto(variables, "ORIGEN_PERMITIDO", "*"),
            ttl_cache_segundos=_entero(variables, "TTL_CACHE_SEGUNDOS", 30, 0, 86_400),
            simbolo=simbolo,
            max_streams=_entero(variables, "MAX_STREAMS", 50, 1, 10_000),
            max_bots=_entero(variables, "MAX_BOTS", 20, 1, 1000),
            data_dir=_texto(variables, "DATA_DIR", "./data"),
            base_datos=_texto(variables, "BASE_DATOS", ""),
            cookie_segura=_booleano(variables, "COOKIE_SEGURA"),
            confiar_proxy=_booleano(variables, "CONFIAR_PROXY"),
            limite_general=_entero(variables, "LIMITE_GENERAL", 600, 1, 1_000_000),
            limite_costosas=_entero(variables, "LIMITE_COSTOSAS", 30, 1, 100_000),
        )


def _texto(variables: Mapping[str, str], nombre: str, por_defecto: str) -> str:
    valor = variables.get(nombre)
    return valor.strip() if valor and valor.strip() else por_defecto


def _entero(variables: Mapping[str, str], nombre: str, por_defecto: int, minimo: int, maximo: int) -> int:
    valor = variables.get(nombre)
    if valor is None or not valor.strip():
        return por_defecto
    try:
        numero = int(valor.strip())
    except ValueError:
        numero = None
    if numero is None or not minimo <= numero <= maximo:
        raise ValueError(f"{nombre} debe ser un número entero entre {minimo} y {maximo}: {valor}")
    return numero


def _booleano(variables: Mapping[str, str], nombre: str) -> bool:
    valor = variables.get(nombre, "").strip().lower()
    if valor in ("", "false", "0", "no"):
        return False
    if valor in ("true", "1", "si", "sí"):
        return True
    raise ValueError(f"{nombre} debe ser true o false: {valor}")
