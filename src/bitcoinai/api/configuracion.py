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
        data_dir: carpeta donde se guarda la simulación (``DATA_DIR``, por defecto ``./data``).
        base_datos: archivo SQLite de usuarios y sesiones (``BASE_DATOS``, por defecto
            ``<DATA_DIR>/bitcoinai.db``).
        cookie_segura: si la cookie de sesión lleva ``Secure`` (``COOKIE_SEGURA``; ponla en
            ``true`` cuando haya HTTPS, como en Railway).
        confiar_proxy: si se cree el encabezado ``X-Forwarded-For`` para saber la IP real
            (``CONFIAR_PROXY``; solo detrás de un proxy propio, como Railway o el frontend).
    """

    puerto: int = 8080
    url_base_binance: str = URL_BASE_POR_DEFECTO
    origen_permitido: str = "*"
    ttl_cache_segundos: int = 30
    simbolo: str = "BTCUSDT"
    max_streams: int = 50
    data_dir: str = "./data"
    base_datos: str = ""
    cookie_segura: bool = False
    confiar_proxy: bool = False

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
            data_dir=_texto(variables, "DATA_DIR", "./data"),
            base_datos=_texto(variables, "BASE_DATOS", ""),
            cookie_segura=_booleano(variables, "COOKIE_SEGURA"),
            confiar_proxy=_booleano(variables, "CONFIAR_PROXY"),
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
