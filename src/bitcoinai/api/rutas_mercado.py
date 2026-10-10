"""Endpoints de mercado: /health, /api/precio y /api/velas.

Los endpoints solo traducen: leen y validan parámetros, llaman al dominio y
arman el JSON del contrato. Son funciones normales (no async): FastAPI las
corre en su grupo de hilos, así una consulta lenta a Binance no bloquea al resto.
"""

import time
from typing import Any

from fastapi import APIRouter

from bitcoinai.api.errores import ApiError
from bitcoinai.api.serializacion import velas_a_json
from bitcoinai.mercado import FuenteDeMercado
from bitcoinai.modelo import Intervalo

CANTIDAD_MAXIMA = 1000
INTERVALO_POR_DEFECTO = "1d"
CANTIDAD_POR_DEFECTO = 200


def crear_rutas_mercado(fuente: FuenteDeMercado, simbolo: str) -> APIRouter:
    """Crea el router con los endpoints de mercado."""
    rutas = APIRouter()

    @rutas.get("/health")
    def salud() -> dict[str, Any]:
        """Indica que el servicio está vivo. Nunca consulta Binance."""
        return {"estado": "ok"}

    @rutas.get("/api/precio")
    def precio() -> dict[str, Any]:
        """Último precio negociado del símbolo configurado."""
        valor = fuente.obtener_precio_actual(simbolo)
        return {"simbolo": simbolo, "precio": valor, "momento": int(time.time() * 1000)}

    @rutas.get("/api/velas")
    def velas(intervalo: str = "", cantidad: str = "") -> dict[str, Any]:
        """Velas del símbolo configurado, de la más antigua a la más reciente."""
        intervalo_elegido = leer_intervalo(intervalo or INTERVALO_POR_DEFECTO)
        cantidad_elegida = leer_cantidad(cantidad or str(CANTIDAD_POR_DEFECTO))
        resultado = fuente.obtener_velas(simbolo, intervalo_elegido, cantidad_elegida)
        return {
            "simbolo": simbolo,
            "intervalo": intervalo_elegido.codigo,
            "cantidad": resultado.tamanio(),
            "velas": velas_a_json(resultado),
        }

    return rutas


def leer_intervalo(texto: str) -> Intervalo:
    """Intervalo de un parámetro, o 400 con los valores permitidos."""
    try:
        return Intervalo.desde_codigo(texto)
    except ValueError:
        raise ApiError(400, f"Parámetro 'intervalo' inválido: '{texto}'. "
                            "Valores permitidos: 1m, 5m, 15m, 1h, 4h, 1d") from None


def leer_cantidad(texto: str) -> int:
    """Cantidad de velas entre 1 y 1000, o 400 con el motivo."""
    try:
        cantidad = int(texto.strip())
    except ValueError:
        cantidad = 0
    if not 1 <= cantidad <= CANTIDAD_MAXIMA:
        raise ApiError(400, f"Parámetro 'cantidad' inválido: '{texto}'. "
                            f"Debe ser un número entero entre 1 y {CANTIDAD_MAXIMA}")
    return cantidad
