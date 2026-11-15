"""Endpoints de la simulación de operaciones (paper trading). Nunca operan con dinero real.

- POST /api/ordenes, GET /api/ordenes?estado=PENDIENTE
- GET /api/ordenes/{id}, DELETE /api/ordenes/{id}
- POST /api/ordenes/procesar, POST /api/ordenes/deshacer
- GET /api/cartera, GET /api/historial?limite=50
- GET /api/exportar/ordenes: el registro de órdenes en CSV, para abrirlo en una hoja de cálculo
- POST /api/bot/iniciar, POST /api/bot/detener, GET /api/bot/estado
- GET /api/estadisticas: operaciones cerradas, aciertos y actividad por día (para las gráficas)
- GET /api/ia/consejo: qué recomienda la IA ahora, según la cartera del usuario

Cada usuario tiene su propia simulación (cartera, órdenes, historial y bot): todos
estos endpoints exigen sesión (401 sin ella) y trabajan sobre la del usuario.

Errores del dominio (ver ``errores.py``): orden inexistente → 404; operación que el
estado no permite → 409; datos inválidos → 400.
"""

import time
from typing import Any, Self

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.csv import contenido_descargable
from bitcoinai.api.errores import ApiError
from bitcoinai.api.rutas_cuentas import Cookies, sesion_de
from bitcoinai.api.serializacion import (
    bot_a_json,
    cartera_a_json,
    consejo_a_json,
    evento_a_json,
    orden_a_json,
)
from bitcoinai.ia.piloto import consejo_para_usuario
from bitcoinai.ia.servicio import DatosInsuficientesError
from bitcoinai.simulacion import (
    ConfiguracionBot,
    EstadoOrden,
    GestorSimulaciones,
    LibroDeOrdenes,
    LimitesPiloto,
    Piloto,
    TipoOrden,
)
from bitcoinai.simulacion.estadisticas import calcular
from bitcoinai.usuarios.servicio import ServicioCuentas

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
    modo: str | None = None


def crear_rutas_simulacion(gestor: GestorSimulaciones, cuentas: ServicioCuentas, config: Configuracion,
                           piloto: Piloto | None = None) -> APIRouter:
    """Crea el router con los endpoints de la simulación de cada usuario."""
    cookies = Cookies(config)

    def exigir_sesion(peticion: Request) -> None:
        """Dependencia de todo el router: comprueba la sesión antes de validar el cuerpo (401 primero)."""
        usuario, _ = sesion_de(peticion, cuentas, cookies)
        peticion.state.usuario_id = usuario.id

    rutas = APIRouter(dependencies=[Depends(exigir_sesion)])

    def usuario_id(peticion: Request) -> int:
        valor: int = peticion.state.usuario_id
        return valor

    def libro_de(peticion: Request) -> LibroDeOrdenes:
        return gestor.libro(usuario_id(peticion))

    @rutas.post("/api/ordenes", status_code=201)
    def crear(cuerpo: CuerpoOrden, peticion: Request) -> dict[str, Any]:
        """Crea una orden pendiente."""
        libro = libro_de(peticion)
        tipo = TipoOrden[(cuerpo.tipo or "").strip().upper()]
        orden = libro.crear_orden(tipo, cuerpo.monto, cuerpo.todo, cuerpo.motivo)
        return orden_a_json(orden)

    @rutas.get("/api/ordenes")
    def listar(peticion: Request, estado: str = "") -> dict[str, Any]:
        """Órdenes: pendientes en orden de cola, la que se procesa y el registro."""
        libro = libro_de(peticion)
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
    def procesar(peticion: Request) -> dict[str, Any]:
        """Ejecuta la orden del frente de la cola."""
        orden = libro_de(peticion).procesar_siguiente()
        if orden is None:
            raise ApiError(409, "No hay órdenes pendientes para procesar")
        return orden_a_json(orden)

    @rutas.post("/api/ordenes/deshacer")
    def deshacer(peticion: Request) -> dict[str, Any]:
        """Deshace la última orden creada si sigue pendiente."""
        orden = libro_de(peticion).deshacer_ultima_orden()
        if orden is None:
            raise ApiError(409, "No hay una orden reciente pendiente que deshacer")
        return orden_a_json(orden)

    @rutas.get("/api/ordenes/{id_orden}")
    def obtener(id_orden: str, peticion: Request) -> dict[str, Any]:
        """Una orden por id."""
        return orden_a_json(libro_de(peticion).obtener(leer_id(id_orden)))

    @rutas.delete("/api/ordenes/{id_orden}")
    def cancelar(id_orden: str, peticion: Request) -> dict[str, Any]:
        """Cancela una orden pendiente."""
        return orden_a_json(libro_de(peticion).cancelar(leer_id(id_orden)))

    @rutas.get("/api/cartera")
    def cartera(peticion: Request) -> dict[str, Any]:
        """Cartera valorada al precio actual."""
        return cartera_a_json(libro_de(peticion).estado_cartera())

    @rutas.get("/api/historial")
    def historial(peticion: Request, limite: str = "") -> dict[str, Any]:
        """Eventos del más reciente al más viejo."""
        libro = libro_de(peticion)
        texto = limite or str(LIMITE_HISTORIAL_POR_DEFECTO)
        try:
            valor = int(texto.strip())
        except ValueError:
            valor = -1
        if not 1 <= valor <= LIMITE_HISTORIAL_MAXIMO:
            raise ApiError(400, f"Parámetro 'limite' inválido: '{texto}'. "
                                f"Debe ser un número entero entre 1 y {LIMITE_HISTORIAL_MAXIMO}")
        return {"eventos": [evento_a_json(e) for e in libro.historial(valor)]}

    @rutas.get("/api/exportar/ordenes")
    def exportar_ordenes(peticion: Request) -> Response:
        """El registro de órdenes de la persona, en CSV y como archivo descargable."""
        libro = libro_de(peticion)
        return Response(
            content=contenido_descargable(libro.ordenes()),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="ordenes.csv"'},
        )

    @rutas.get("/api/estadisticas")
    def estadisticas(peticion: Request) -> dict[str, Any]:
        """Lo que piden las gráficas del panel, calculado con las órdenes ejecutadas."""
        libro = libro_de(peticion)
        cartera_actual = libro.estado_cartera()
        e = calcular(libro.ordenes(EstadoOrden.EJECUTADA), cartera_actual.saldo_inicial, libro.comision,
                     int(time.time() * 1000))
        return {
            "operaciones": [{"idOrden": o.id_orden, "tiempo": o.tiempo, "ganancia": o.ganancia,
                             "rentabilidad": o.rentabilidad, "origen": o.origen} for o in e.operaciones],
            "actividad": [{"dia": a.dia, "compras": a.compras, "ventas": a.ventas, "volumen": a.volumen}
                          for a in e.actividad],
            "resumen": {
                "cerradas": e.ganadoras + e.perdedoras, "ganadoras": e.ganadoras, "perdedoras": e.perdedoras,
                "tasaAcierto": e.tasa_acierto, "gananciaPromedio": e.ganancia_promedio, "mejor": e.mejor,
                "peor": e.peor, "volumenTotal": e.volumen_total,
            },
            "porOrigen": [{"origen": o, "ordenes": e.por_origen[o], "ganancia": e.ganancia_por_origen[o]}
                          for o in e.por_origen],
            "reparto": {"usdt": cartera_actual.saldo_usdt, "btc": cartera_actual.valor_btc},
        }

    @rutas.get("/api/ia/consejo")
    def consejo(peticion: Request) -> dict[str, Any]:
        """Qué haría la IA ahora con la cartera de quien pregunta (velas de 1 hora)."""
        if piloto is None:
            raise ApiError(503, "La IA no está disponible en este servidor")
        libro = libro_de(peticion)
        bot = gestor.bot(usuario_id(peticion)).estado().configuracion
        try:
            c = piloto.aconsejar("1h", LimitesPiloto(bot.riesgo, bot.stop_loss, bot.take_profit))
        except DatosInsuficientesError as error:
            raise ApiError(503, str(error)) from None
        accion, titulo, texto = consejo_para_usuario(c, libro.estado_cartera(c.precio).btc > 0)
        return {"accion": accion, "titulo": titulo, "texto": texto, "decision": consejo_a_json(c),
                "aviso": "Es una simulación: la IA puede equivocarse y no es asesoría financiera."}

    @rutas.post("/api/bot/iniciar")
    def iniciar_bot(peticion: Request, cuerpo: CuerpoBot | None = None) -> dict[str, Any]:
        """Pone en marcha el bot del usuario (configuración opcional en el cuerpo)."""
        usuario = usuario_id(peticion)
        datos = cuerpo.model_dump(exclude_none=True) if cuerpo is not None else {}
        try:
            configuracion = ConfiguracionBot(**datos)
        except ValueError as error:
            raise ApiError(400, str(error)) from None
        return bot_a_json(gestor.iniciar_bot(usuario, configuracion))

    @rutas.post("/api/bot/detener")
    def detener_bot(peticion: Request) -> dict[str, Any]:
        """Detiene el bot (si ya estaba detenido, no hace nada)."""
        return bot_a_json(gestor.bot(usuario_id(peticion)).detener())

    @rutas.get("/api/bot/estado")
    def estado_bot(peticion: Request) -> dict[str, Any]:
        """Estado del bot y su última decisión."""
        return bot_a_json(gestor.bot(usuario_id(peticion)).estado())

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
