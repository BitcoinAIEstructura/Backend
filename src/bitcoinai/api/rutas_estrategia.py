"""Endpoints de estrategias: /api/senal y /api/backtest."""

import time
from typing import Any

from fastapi import APIRouter, Request

from bitcoinai.api.errores import ApiError
from bitcoinai.api.rutas_mercado import (
    CANTIDAD_MAXIMA,
    CANTIDAD_POR_DEFECTO,
    INTERVALO_POR_DEFECTO,
    leer_cantidad,
    leer_intervalo,
)
from bitcoinai.api.serializacion import backtest_a_json, decision_a_json, pronostico_a_json, validacion_a_json
from bitcoinai.estrategia import (
    AVISO,
    FRACCION_POR_DEFECTO,
    Backtester,
    Estrategia,
    Pronostico,
    ValidacionEntrenamientoPrueba,
    candidatos,
    crear_estrategia,
)
from bitcoinai.estructuras import ListaDoble
from bitcoinai.mercado import FuenteDeMercado, velas_cerradas
from bitcoinai.modelo import Vela


def crear_rutas_estrategia(fuente: FuenteDeMercado, simbolo: str) -> APIRouter:
    """Crea el router con los endpoints de estrategias."""
    rutas = APIRouter()

    def velas_para(intervalo: str, cantidad: str, cantidad_por_defecto: int) -> tuple[str, ListaDoble[Vela]]:
        """Valida intervalo y cantidad, y trae las velas ya cerradas (sin la del periodo en curso)."""
        intervalo_elegido = leer_intervalo(intervalo or INTERVALO_POR_DEFECTO)
        cantidad_elegida = leer_cantidad(cantidad or str(cantidad_por_defecto))
        velas = fuente.obtener_velas(simbolo, intervalo_elegido, cantidad_elegida)
        return intervalo_elegido.codigo, velas_cerradas(velas, int(time.time() * 1000))

    @rutas.get("/api/senal")
    def senal(peticion: Request, estrategia: str = "", intervalo: str = "", cantidad: str = "") -> dict[str, Any]:
        """Decisión y pronóstico más recientes de una estrategia (por defecto la combinada)."""
        elegida = leer_estrategia(estrategia, peticion)
        codigo, velas = velas_para(intervalo, cantidad, CANTIDAD_POR_DEFECTO)
        decision = elegida.evaluar(velas)
        return {
            "simbolo": simbolo,
            "intervalo": codigo,
            "estrategia": elegida.nombre(),
            "parametros": elegida.parametros(),
            "velasAnalizadas": velas.tamanio(),
            "decision": decision_a_json(decision),
            "pronostico": pronostico_a_json(Pronostico.desde(elegida, velas, decision)),
        }

    @rutas.get("/api/backtest")
    def backtest(peticion: Request, estrategia: str = "", capital: str = "", comision: str = "",
                 entrenamiento: str = "", intervalo: str = "", cantidad: str = "") -> dict[str, Any]:
        """Backtest con los parámetros pedidos sobre todo el periodo, más la validación 70/30."""
        elegida = leer_estrategia(estrategia, peticion)
        capital_inicial = leer_decimal("capital", capital, 1000, 1, 1_000_000_000, "1 y 1000000000")
        comision_elegida = leer_decimal("comision", comision, 0.001, 0, 0.05, "0 y 0.05")
        fraccion = leer_decimal("entrenamiento", entrenamiento, FRACCION_POR_DEFECTO, 0.5, 0.9, "0.5 y 0.9")
        codigo, velas = velas_para(intervalo, cantidad, CANTIDAD_MAXIMA)

        backtester = Backtester(capital_inicial, comision_elegida)
        resultado = backtester.ejecutar(elegida, velas)
        validacion = ValidacionEntrenamientoPrueba(backtester, fraccion).ejecutar(candidatos(elegida.nombre()), velas)
        return {
            "simbolo": simbolo,
            "intervalo": codigo,
            "estrategia": elegida.nombre(),
            "parametros": elegida.parametros(),
            "resultado": backtest_a_json(resultado),
            "validacion": validacion_a_json(validacion),
            "aviso": AVISO,
        }

    return rutas


def leer_estrategia(nombre: str, peticion: Request) -> Estrategia:
    """Estrategia pedida (por defecto la combinada) con los parámetros de la URL, o 400."""
    try:
        return crear_estrategia(nombre or "combinada", dict(peticion.query_params))
    except ValueError as error:
        raise ApiError(400, str(error)) from None


def leer_decimal(nombre: str, texto: str, por_defecto: float, minimo: float, maximo: float, rango: str) -> float:
    """Número decimal de un parámetro, o 400 con el rango permitido."""
    if not texto:
        return por_defecto
    try:
        valor = float(texto.strip())
    except ValueError:
        valor = float("nan")
    if not minimo <= valor <= maximo:
        raise ApiError(400, f"Parámetro '{nombre}' inválido: '{texto}'. Debe ser un número entre {rango}")
    return valor
