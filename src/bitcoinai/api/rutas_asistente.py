"""POST /api/asistente: el chat con el bot. Exige sesión y responde con los datos de esa persona.

El asistente nunca enciende ni detiene el bot por su cuenta: si se lo piden, la respuesta
trae una ``accion`` y el frontend la muestra como botón; tocarlo llama a /api/bot/….

Con un ``Conversador`` (hay ``ANTHROPIC_API_KEY``), Claude escribe el texto con los datos de
práctica y el ``historial`` reciente, y puede proponer una acción (orden, bot, alerta o página).
Si la propuesta pasa la revisión de ``propuestas.validar``, reemplaza la acción de las reglas;
si no, queda la de las reglas. Las sugerencias siguen saliendo del asistente de reglas. Si Claude
no responde, queda el texto de las reglas (``fuente``: "reglas").
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.errores import ApiError
from bitcoinai.api.rutas_cuentas import Cookies, sesion_de
from bitcoinai.asistente import Accion, Asistente, DatosUsuario
from bitcoinai.asistente.asistente import LARGO_MAXIMO
from bitcoinai.asistente.contexto import armar_contexto
from bitcoinai.asistente.conversador import LARGO_MAXIMO_TURNO, TURNOS_DE_HISTORIAL, Conversador, Turno
from bitcoinai.asistente.propuestas import validar
from bitcoinai.mercado import MercadoError
from bitcoinai.simulacion import ConsejoPiloto, EstadoOrden, GestorSimulaciones, LimitesPiloto
from bitcoinai.usuarios.servicio import ServicioCuentas


class TurnoChat(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    rol: str
    texto: str = Field(max_length=LARGO_MAXIMO_TURNO)


class CuerpoMensaje(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    mensaje: str | None = None
    # Los mensajes anteriores del chat (solo los usa Claude); se aceptan hasta 20 y se usan los últimos.
    historial: list[TurnoChat] = Field(default_factory=list, max_length=2 * TURNOS_DE_HISTORIAL)


def crear_rutas_asistente(gestor: GestorSimulaciones, cuentas: ServicioCuentas, config: Configuracion,
                          asistente: Asistente | None = None,
                          conversador: Conversador | None = None) -> APIRouter:
    cookies = Cookies(config)

    def exigir_sesion(peticion: Request) -> None:
        """La sesión se revisa antes que el cuerpo: sin ella, 401 aunque el cuerpo esté mal."""
        usuario, _ = sesion_de(peticion, cuentas, cookies)
        peticion.state.usuario_id = usuario.id

    rutas = APIRouter(dependencies=[Depends(exigir_sesion)])
    elegido = asistente or Asistente()

    def consejo_de(usuario_id: int) -> ConsejoPiloto | None:
        """El consejo de la IA para el contexto de Claude; si no se puede, se habla sin él."""
        if gestor.piloto is None:
            return None
        c = gestor.bot(usuario_id).estado().configuracion
        try:
            return gestor.piloto.aconsejar("1h", LimitesPiloto(c.riesgo, c.stop_loss, c.take_profit))
        except Exception:  # sin velas o sin mercado: Claude responde con el resto de los datos
            return None

    @rutas.post("/api/asistente")
    def conversar(cuerpo: CuerpoMensaje, peticion: Request) -> dict[str, Any]:
        """Responde un mensaje: ``{intencion, respuesta, accion, sugerencias}``."""
        usuario_id: int = peticion.state.usuario_id
        mensaje = (cuerpo.mensaje or "").strip()
        if not mensaje:
            raise ApiError(400, "Escribe un mensaje para el bot")
        if len(mensaje) > LARGO_MAXIMO:
            raise ApiError(400, f"El mensaje es demasiado largo (máximo {LARGO_MAXIMO} caracteres)")
        libro = gestor.libro(usuario_id)
        try:
            cartera = libro.estado_cartera()
        except MercadoError:
            cartera = None  # sin precio igual se puede hablar del bot
        datos = DatosUsuario(cartera, gestor.bot(usuario_id).estado(),
                             libro.ordenes(EstadoOrden.PENDIENTE).tamanio())
        r = elegido.responder(mensaje, datos)
        texto, fuente, accion = r.texto, "reglas", r.accion
        if conversador is not None:
            historial = tuple(Turno(t.rol, t.texto) for t in cuerpo.historial if t.rol in ("usuario", "bot"))
            contexto = armar_contexto(datos, libro.ordenes(EstadoOrden.EJECUTADA), consejo_de(usuario_id))
            de_claude = conversador.responder(usuario_id, mensaje, historial, contexto)
            if de_claude is not None:
                propuesta = None if de_claude.propuesta is None else validar(
                    *de_claude.propuesta, datos, datos.bot.piloto_disponible)
                if propuesta is not None:
                    accion = propuesta
                if de_claude.texto:
                    texto, fuente = de_claude.texto, "ia"
                elif propuesta is not None:
                    texto, fuente = "Te propongo esto. Si te parece, confírmalo con el botón.", "ia"
        return {"intencion": r.intencion, "respuesta": texto, "accion": _accion_json(accion),
                "sugerencias": list(r.sugerencias), "fuente": fuente}

    return rutas


def _accion_json(a: Accion | None) -> dict[str, Any] | None:
    """La acción como la recibe el frontend (``orden``, ``alerta`` y ``modo`` van en null si no aplican)."""
    if a is None:
        return None
    orden = None if a.orden is None else {"tipo": a.orden.tipo, "monto": a.orden.monto, "todo": a.orden.todo}
    alerta = None if a.alerta is None else {"tipo": a.alerta.tipo, "precio": a.alerta.precio}
    return {"tipo": a.tipo, "etiqueta": a.etiqueta, "ruta": a.ruta, "orden": orden, "alerta": alerta,
            "modo": a.modo}
