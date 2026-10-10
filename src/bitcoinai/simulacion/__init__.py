"""Simulación de operaciones (paper trading): cartera, libro de órdenes y bot. Sin dinero real."""

from bitcoinai.simulacion.bot import COMPRA_MINIMA, BotSimulado, ConfiguracionBot, EstadoBot
from bitcoinai.simulacion.cartera import SALDO_INICIAL_POR_DEFECTO, Cartera, Ejecucion, EstadoCartera
from bitcoinai.simulacion.libro import COMISION_POR_DEFECTO, LibroDeOrdenes
from bitcoinai.simulacion.modelo import (
    EstadoOrden,
    Evento,
    OperacionInvalidaError,
    OperacionRechazadaError,
    Orden,
    OrdenNoEncontradaError,
    TipoEvento,
    TipoOrden,
)

__all__ = (
    "COMISION_POR_DEFECTO",
    "COMPRA_MINIMA",
    "SALDO_INICIAL_POR_DEFECTO",
    "BotSimulado",
    "Cartera",
    "ConfiguracionBot",
    "Ejecucion",
    "EstadoBot",
    "EstadoCartera",
    "EstadoOrden",
    "Evento",
    "LibroDeOrdenes",
    "OperacionInvalidaError",
    "OperacionRechazadaError",
    "Orden",
    "OrdenNoEncontradaError",
    "TipoEvento",
    "TipoOrden",
)
