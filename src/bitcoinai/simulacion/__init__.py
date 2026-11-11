"""Simulación de operaciones (paper trading): cartera, libro de órdenes y bot. Sin dinero real."""

from bitcoinai.simulacion.bot import COMPRA_MINIMA, BotSimulado, ConfiguracionBot, EstadoBot
from bitcoinai.simulacion.cartera import SALDO_INICIAL_POR_DEFECTO, Cartera, Ejecucion, EstadoCartera
from bitcoinai.simulacion.gestor import MAXIMO_BOTS_POR_DEFECTO, GestorSimulaciones, SimulacionUsuario
from bitcoinai.simulacion.interfaces import (
    AlmacenSimulacion,
    ConsejoPiloto,
    DatosCartera,
    EstadoSimulacion,
    LimitesPiloto,
    Piloto,
    PublicadorEventos,
    SinPublicar,
)
from bitcoinai.simulacion.libro import COMISION_POR_DEFECTO, EVENTOS_GUARDADOS_MAXIMO, LibroDeOrdenes
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
    "EVENTOS_GUARDADOS_MAXIMO",
    "MAXIMO_BOTS_POR_DEFECTO",
    "SALDO_INICIAL_POR_DEFECTO",
    "AlmacenSimulacion",
    "BotSimulado",
    "Cartera",
    "ConfiguracionBot",
    "ConsejoPiloto",
    "DatosCartera",
    "Ejecucion",
    "EstadoBot",
    "EstadoCartera",
    "EstadoOrden",
    "EstadoSimulacion",
    "GestorSimulaciones",
    "Evento",
    "LibroDeOrdenes",
    "LimitesPiloto",
    "OperacionInvalidaError",
    "OperacionRechazadaError",
    "Orden",
    "OrdenNoEncontradaError",
    "Piloto",
    "PublicadorEventos",
    "SimulacionUsuario",
    "SinPublicar",
    "TipoEvento",
    "TipoOrden",
)
