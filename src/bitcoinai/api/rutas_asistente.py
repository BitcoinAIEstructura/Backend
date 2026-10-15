"""POST /api/asistente: el chat con el bot. Exige sesión y responde con los datos de esa persona.

El asistente nunca enciende ni detiene el bot por su cuenta: si se lo piden, la respuesta
trae una ``accion`` y el frontend la muestra como botón; tocarlo llama a /api/bot/….
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.errores import ApiError
from bitcoinai.api.rutas_cuentas import Cookies, sesion_de
from bitcoinai.asistente import Asistente, DatosUsuario
from bitcoinai.asistente.asistente import LARGO_MAXIMO
from bitcoinai.mercado import MercadoError
from bitcoinai.simulacion import EstadoOrden, GestorSimulaciones
from bitcoinai.usuarios.servicio import ServicioCuentas


class CuerpoMensaje(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    mensaje: str | None = None


def crear_rutas_asistente(gestor: GestorSimulaciones, cuentas: ServicioCuentas, config: Configuracion,
                          asistente: Asistente | None = None) -> APIRouter:
    cookies = Cookies(config)

    def exigir_sesion(peticion: Request) -> None:
        """La sesión se revisa antes que el cuerpo: sin ella, 401 aunque el cuerpo esté mal."""
        usuario, _ = sesion_de(peticion, cuentas, cookies)
        peticion.state.usuario_id = usuario.id

    rutas = APIRouter(dependencies=[Depends(exigir_sesion)])
    elegido = asistente or Asistente()

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
        accion = None if r.accion is None else {
            "tipo": r.accion.tipo, "etiqueta": r.accion.etiqueta, "ruta": r.accion.ruta}
        return {"intencion": r.intencion, "respuesta": r.texto, "accion": accion,
                "sugerencias": list(r.sugerencias)}

    return rutas
