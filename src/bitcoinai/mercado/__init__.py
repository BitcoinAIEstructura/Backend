"""Datos de mercado: cliente de Binance, caché y validación de velas."""

from bitcoinai.mercado.cache import CacheMercado
from bitcoinai.mercado.cliente_binance import (
    LIMITE_POR_PETICION,
    MENSAJE_REGION_RESTRINGIDA,
    URL_BASE_POR_DEFECTO,
    ClienteBinance,
    convertir_klines,
    normalizar_simbolo,
    resolver_url_base,
)
from bitcoinai.mercado.errores import MercadoError
from bitcoinai.mercado.fuente import FuenteDeMercado
from bitcoinai.mercado.validacion import validar_velas, velas_cerradas

__all__ = (
    "LIMITE_POR_PETICION",
    "MENSAJE_REGION_RESTRINGIDA",
    "URL_BASE_POR_DEFECTO",
    "CacheMercado",
    "ClienteBinance",
    "FuenteDeMercado",
    "MercadoError",
    "convertir_klines",
    "normalizar_simbolo",
    "resolver_url_base",
    "validar_velas",
    "velas_cerradas",
)
