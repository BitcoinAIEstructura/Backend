"""Modelo de la simulación: órdenes, eventos y errores."""

import dataclasses
from dataclasses import dataclass
from enum import Enum


class TipoOrden(Enum):
    """Tipo de orden simulada."""

    COMPRA = "COMPRA"
    VENTA = "VENTA"


class EstadoOrden(Enum):
    """Estado de una orden en su ciclo de vida."""

    PENDIENTE = "PENDIENTE"
    """Esperando en la cola."""
    PROCESANDO = "PROCESANDO"
    """Sacada de la cola; se está consultando el precio para ejecutarla."""
    EJECUTADA = "EJECUTADA"
    """Ejecutada: la cartera ya cambió."""
    CANCELADA = "CANCELADA"
    """Cancelada o deshecha antes de ejecutarse."""
    RECHAZADA = "RECHAZADA"
    """No se pudo ejecutar (saldo o BTC insuficiente)."""


class TipoEvento(Enum):
    """Tipos de evento del historial."""

    ORDEN_CREADA = "ORDEN_CREADA"
    ORDEN_EJECUTADA = "ORDEN_EJECUTADA"
    ORDEN_CANCELADA = "ORDEN_CANCELADA"
    ORDEN_DESHECHA = "ORDEN_DESHECHA"
    ORDEN_RECHAZADA = "ORDEN_RECHAZADA"
    DECISION_BOT = "DECISION_BOT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    BOT_INICIADO = "BOT_INICIADO"
    BOT_DETENIDO = "BOT_DETENIDO"
    ERROR_BOT = "ERROR_BOT"


@dataclass(frozen=True, slots=True)
class Evento:
    """Algo que pasó en la simulación, para el historial.

    Atributos:
        momento: cuándo pasó (ms desde 1970, UTC).
        tipo: qué pasó.
        id_orden: orden relacionada, o None.
        descripcion: una frase en español.
    """

    momento: int
    tipo: TipoEvento
    id_orden: int | None
    descripcion: str


@dataclass(frozen=True, slots=True)
class Orden:
    """Orden simulada. Es inmutable: cada cambio de estado crea una orden nueva con el mismo id.

    Atributos:
        id: número único, creciente.
        tipo: compra o venta.
        monto: USDT a comprar o a vender; None en una venta de todo el BTC hasta que
            se ejecuta (ahí pasa a ser lo obtenido).
        todo: True si es una venta de todo el BTC.
        estado: estado actual.
        creada_en: cuándo se creó (ms).
        ejecutada_en: cuándo se procesó (ejecutada o rechazada), o None.
        precio_ejecucion, cantidad_btc, comision: resultado de la ejecución, o None.
        motivo: por qué se creó ("manual", "señal del bot: …", "stop-loss: …").
        detalle: resultado o razón del rechazo o la cancelación, o None.
    """

    id: int
    tipo: TipoOrden
    monto: float | None
    todo: bool
    estado: EstadoOrden
    creada_en: int
    ejecutada_en: int | None = None
    precio_ejecucion: float | None = None
    cantidad_btc: float | None = None
    comision: float | None = None
    motivo: str = "manual"
    detalle: str | None = None

    def con_estado(self, estado: EstadoOrden, detalle: str | None) -> "Orden":
        """La misma orden con otro estado y detalle."""
        return dataclasses.replace(self, estado=estado, detalle=detalle)


class OperacionRechazadaError(Exception):
    """La cartera no puede ejecutar una operación (por ejemplo, saldo insuficiente)."""


class OrdenNoEncontradaError(Exception):
    """No existe una orden con ese id."""

    def __init__(self, id_orden: int) -> None:
        super().__init__(f"No existe la orden #{id_orden}")


class OperacionInvalidaError(Exception):
    """La operación no se puede hacer en el estado actual.

    Por ejemplo: cancelar una orden ya ejecutada, o iniciar el bot dos veces.
    """
