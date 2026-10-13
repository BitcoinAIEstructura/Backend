"""Alertas de precio de cada usuario (exigen sesión).

- POST /api/alertas ``{"tipo":"SUBE_A","precio":90000}`` → 201 con la alerta
- GET /api/alertas → ``{"activas": n, "alertas": [...]}`` (las 50 más nuevas)
- DELETE /api/alertas/{id} → 204

Cuando una alerta se cumple, su dueño recibe ``event: alerta`` por /api/stream.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict

from bitcoinai.alertas.servicio import AlertaInvalidaError, AlertaNoEncontradaError, ServicioAlertas
from bitcoinai.alertas.tablero import Alerta, EstadoAlerta
from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.errores import ApiError
from bitcoinai.api.rutas_cuentas import Cookies, sesion_de
from bitcoinai.mercado import FuenteDeMercado
from bitcoinai.usuarios.servicio import ServicioCuentas


class CuerpoAlerta(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    tipo: str
    precio: float


def alerta_a_json(a: Alerta) -> dict[str, Any]:
    return {"id": a.id, "tipo": a.tipo.value, "precio": a.precio, "estado": a.estado.value,
            "creadaEn": a.creada_en, "disparadaEn": a.disparada_en, "precioDisparo": a.precio_disparo}


def crear_rutas_alertas(alertas: ServicioAlertas, fuente: FuenteDeMercado, simbolo: str,
                        cuentas: ServicioCuentas, config: Configuracion) -> APIRouter:
    cookies = Cookies(config)

    def exigir_sesion(peticion: Request) -> None:
        usuario, _ = sesion_de(peticion, cuentas, cookies)
        peticion.state.usuario_id = usuario.id

    rutas = APIRouter(dependencies=[Depends(exigir_sesion)])

    @rutas.post("/api/alertas", status_code=201)
    def crear(cuerpo: CuerpoAlerta, peticion: Request) -> dict[str, Any]:
        try:
            alerta = alertas.crear(peticion.state.usuario_id, cuerpo.tipo, cuerpo.precio,
                                   fuente.obtener_precio_actual(simbolo))
        except AlertaInvalidaError as error:
            raise ApiError(400, str(error)) from None
        return alerta_a_json(alerta)

    @rutas.get("/api/alertas")
    def listar(peticion: Request) -> dict[str, Any]:
        lista = alertas.listar(peticion.state.usuario_id)
        return {"activas": sum(1 for a in lista if a.estado is EstadoAlerta.ACTIVA),
                "alertas": [alerta_a_json(a) for a in lista]}

    @rutas.delete("/api/alertas/{id_alerta}", status_code=204)
    def cancelar(id_alerta: str, peticion: Request) -> Response:
        try:
            alertas.cancelar(peticion.state.usuario_id, int(id_alerta))
        except (ValueError, AlertaNoEncontradaError):
            raise ApiError(404, f"No tienes una alerta activa #{id_alerta}") from None
        return Response(status_code=204)

    return rutas
