"""Estrategias de señales, pronóstico, backtesting y validación entrenamiento/prueba."""

from bitcoinai.estrategia.apoyo import CONFIANZA_NEUTRA
from bitcoinai.estrategia.backtest import Backtester, OperacionCerrada, ResultadoBacktest
from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estrategia.combinada import Componente, EstrategiaCombinada
from bitcoinai.estrategia.cruce import CruceDeMedias
from bitcoinai.estrategia.fabrica import NOMBRES, candidatos, crear_estrategia
from bitcoinai.estrategia.macd import EstrategiaMacd
from bitcoinai.estrategia.modelo import Decision, Direccion, Senal
from bitcoinai.estrategia.pronostico import AVISO, Pronostico, direccion_de
from bitcoinai.estrategia.rsi import EstrategiaRsi
from bitcoinai.estrategia.validacion import (
    FRACCION_POR_DEFECTO,
    ResultadoValidacion,
    ResumenCandidato,
    ValidacionEntrenamientoPrueba,
)

__all__ = (
    "AVISO",
    "CONFIANZA_NEUTRA",
    "FRACCION_POR_DEFECTO",
    "NOMBRES",
    "Backtester",
    "Componente",
    "CruceDeMedias",
    "Decision",
    "Direccion",
    "Estrategia",
    "EstrategiaCombinada",
    "EstrategiaMacd",
    "EstrategiaRsi",
    "OperacionCerrada",
    "Pronostico",
    "ResultadoBacktest",
    "ResultadoValidacion",
    "ResumenCandidato",
    "Senal",
    "ValidacionEntrenamientoPrueba",
    "candidatos",
    "crear_estrategia",
    "direccion_de",
)
