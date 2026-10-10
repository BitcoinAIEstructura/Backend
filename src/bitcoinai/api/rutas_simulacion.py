"""Endpoints de la simulación de operaciones (paper trading). Nunca operan con dinero real.

- POST /api/ordenes, GET /api/ordenes?estado=PENDIENTE
- GET /api/ordenes/{id}, DELETE /api/ordenes/{id}
- POST /api/ordenes/procesar, POST /api/ordenes/deshacer
- GET /api/cartera, GET /api/historial?limite=50
- POST /api/bot/iniciar, POST /api/bot/detener, GET /api/bot/estado

Errores del dominio (ver ``errores.py``): orden inexistente → 404; operación que el
estado no permite → 409; datos inválidos → 400.
"""

from typing import Any, Self

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from bitcoinai.api.errores import ApiError
from bitcoinai.api.serializacion import (
    bot_a_json,
    cartera_a_json,
    evento_a_json,
    orden_a_json,
)
from bitcoinai.simulacion import BotSimulado, ConfiguracionBot, EstadoOrden, LibroDeOrdenes, TipoOrden

MONTO_MAXIMO = 1_000_000_000
LIMITE_HISTORIAL_POR_DEFECTO = 50
LIMITE_HISTORIAL_MAXIMO = 500


class CuerpoOrden(BaseModel):
    """Cuerpo de POST /api/ordenes.

    ``{"tipo":"COMPRA","monto":500}``, ``{"tipo":"VENTA","monto":200}`` o
    ``{"tipo":"VENTA","todo":true}``; ``motivo`` es opcional. En modo estricto:
    ``"500"`` (texto) no se acepta como número.
    """

    model_config = ConfigDict(strict=True, extra="ignore")

    tipo: str | None = None
    monto: float | None = None
    todo: bool = False
    motivo: str | None = None

    @model_validator(mode="after")
    def validar(self) -> Self:
        """Reglas entre campos, con mensajes en español."""
        if self.tipo is None:
            raise ValueError("Falta el campo 'tipo' (COMPRA o VENTA)")
        if self.tipo.strip().upper() not in ("COMPRA", "VENTA"):
            raise ValueError(f"Campo 'tipo' inválido: '{self.tipo}'. Valores permitidos: COMPRA, VENTA")
        if self.todo:
            if self.tipo.strip().upper() != "VENTA":
                raise ValueError("El campo 'todo' solo se usa en órdenes de VENTA")
            if self.monto is not None:
                raise ValueError("Con 'todo': true no se indica 'monto'")
        elif self.monto is None:
            raise ValueError("Falta el campo 'monto' (USDT, mayor que 0)")
        elif not 0 < self.monto <= MONTO_MAXIMO:
            raise ValueError(f"El campo 'monto' debe ser mayor que 0 y como máximo {MONTO_MAXIMO}")
        return self


class CuerpoBot(BaseModel):
    """Cuerpo opcional de POST /api/bot/iniciar; los campos que falten toman el valor por defecto."""

    model_config = ConfigDict(strict=True, extra="ignore", populate_by_name=True)

    segundos_entre_ciclos: int | None = Field(None, alias="segundosEntreCiclos")
    intervalo: str | None = None
    cantidad_velas: int | None = Field(None, alias="cantidadVelas")
    riesgo: float | None = None
    stop_loss: float | None = Field(None, alias="stopLoss")
    take_profit: float | None = Field(None, alias="takeProfit")


def crear_rutas_simulacion(libro: LibroDeOrdenes, bot: BotSimulado) -> APIRouter:
    """Crea el router con los endpoints de la simulación."""
    rutas = APIRouter()

    @rutas.post("/api/ordenes", status_code=201)
    def crear(cuerpo: CuerpoOrden) -> dict[str, Any]:
        """Crea una orden pendiente."""
        tipo = TipoOrden[(cuerpo.tipo or "").strip().upper()]
        orden = libro.crear_orden(tipo, cuerpo.monto, cuerpo.todo, cuerpo.motivo)
        return orden_a_json(orden)

    @rutas.get("/api/ordenes")
    def listar(estado: str = "") -> dict[str, Any]:
        """Órdenes: pendientes en orden de cola, la que se procesa y el registro."""
        filtro = None
        if estado:
            try:
                filtro = EstadoOrden[estado.strip().upper()]
            except KeyError:
                raise ApiError(400, f"Parámetro 'estado' inválido: '{estado}'. Valores permitidos: "
                                    "PENDIENTE, PROCESANDO, EJECUTADA, CANCELADA, RECHAZADA") from None
        ordenes = libro.ordenes(filtro)
        return {"cantidad": ordenes.tamanio(), "ordenes": [orden_a_json(o) for o in ordenes]}

    @rutas.post("/api/ordenes/procesar")
    def procesar() -> dict[str, Any]:
        """Ejecuta la orden del frente de la cola."""
        orden = libro.procesar_siguiente()
        if orden is None:
            raise ApiError(409, "No hay órdenes pendientes para procesar")
        return orden_a_json(orden)

    @rutas.post("/api/ordenes/deshacer")
    def deshacer() -> dict[str, Any]:
        """Deshace la última orden creada si sigue pendiente."""
        orden = libro.deshacer_ultima_orden()
        if orden is None:
            raise ApiError(409, "No hay una orden reciente pendiente que deshacer")
        return orden_a_json(orden)

    @rutas.get("/api/ordenes/{id_orden}")
    def obtener(id_orden: str) -> dict[str, Any]:
        """Una orden por id."""
        return orden_a_json(libro.obtener(leer_id(id_orden)))

    @rutas.delete("/api/ordenes/{id_orden}")
    def cancelar(id_orden: str) -> dict[str, Any]:
        """Cancela una orden pendiente."""
        return orden_a_json(libro.cancelar(leer_id(id_orden)))

    @rutas.get("/api/cartera")
    def cartera() -> dict[str, Any]:
        """Cartera valorada al precio actual."""
        return cartera_a_json(libro.estado_cartera())

    @rutas.get("/api/historial")
    def historial(limite: str = "") -> dict[str, Any]:
        """Eventos del más reciente al más viejo."""
        texto = limite or str(LIMITE_HISTORIAL_POR_DEFECTO)
        try:
            valor = int(texto.strip())
        except ValueError:
            valor = -1
        if not 1 <= valor <= LIMITE_HISTORIAL_MAXIMO:
            raise ApiError(400, f"Parámetro 'limite' inválido: '{texto}'. "
                                f"Debe ser un número entero entre 1 y {LIMITE_HISTORIAL_MAXIMO}")
        return {"eventos": [evento_a_json(e) for e in libro.historial(valor)]}

    @rutas.post("/api/bot/iniciar")
    def iniciar_bot(cuerpo: CuerpoBot | None = None) -> dict[str, Any]:
        """Pone en marcha el bot (configuración opcional en el cuerpo)."""
        datos = cuerpo.model_dump(exclude_none=True) if cuerpo is not None else {}
        try:
            configuracion = ConfiguracionBot(**datos)
        except ValueError as error:
            raise ApiError(400, str(error)) from None
        return bot_a_json(bot.iniciar(configuracion))

    @rutas.post("/api/bot/detener")
    def detener_bot() -> dict[str, Any]:
        """Detiene el bot (si ya estaba detenido, no hace nada)."""
        return bot_a_json(bot.detener())

    @rutas.get("/api/bot/estado")
    def estado_bot() -> dict[str, Any]:
        """Estado del bot y su última decisión."""
        return bot_a_json(bot.estado())

    return rutas


def leer_id(texto: str) -> int:
    """Id de orden positivo, o 400."""
    try:
        valor = int(texto)
    except ValueError:
        valor = 0
    if valor < 1:
        raise ApiError(400, f"Id de orden inválido: '{texto}'. Debe ser un número entero positivo")
    return valor
