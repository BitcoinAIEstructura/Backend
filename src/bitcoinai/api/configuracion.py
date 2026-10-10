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
    """Configuración del backend. No contiene secretos: todo lo que usa es público.

    Atributos:
        puerto: puerto HTTP (``PORT``, por defecto 8080; Railway lo inyecta).
        url_base_binance: URL base de Binance (``BINANCE_BASE_URL``).
        origen_permitido: origen permitido para CORS (``ORIGEN_PERMITIDO``, por defecto ``*``).
        ttl_cache_segundos: segundos de caché de los datos de mercado (``TTL_CACHE_SEGUNDOS``, por defecto 30).
        simbolo: par de mercado (``SIMBOLO``, por defecto BTCUSDT).
    """

    puerto: int = 8080
    url_base_binance: str = URL_BASE_POR_DEFECTO
    origen_permitido: str = "*"
    ttl_cache_segundos: int = 30
    simbolo: str = "BTCUSDT"

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
