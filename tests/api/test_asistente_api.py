"""POST /api/asistente con una FuenteFalsa a precio 100."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.mercado import MercadoError
from bitcoinai.simulacion import GestorSimulaciones
from tests.api.test_simulacion_api import post, registrado
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import crear_entorno


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa()


@pytest.fixture
def gestor(fuente: FuenteFalsa) -> Iterator[GestorSimulaciones]:
    g = GestorSimulaciones(fuente, "BTCUSDT")
    yield g
    g.detener_todos()


@pytest.fixture
def app(fuente: FuenteFalsa, gestor: GestorSimulaciones) -> FastAPI:
    return crear_app(Configuracion(), fuente, cuentas=crear_entorno().servicio, gestor=gestor)


def test_exige_sesion_antes_que_el_cuerpo(app: FastAPI) -> None:
    assert post(TestClient(app), "/api/asistente", '{"mensaje":5}').status_code == 401


def test_responde_con_los_datos_de_la_persona(app: FastAPI) -> None:
    c = registrado(app)
    post(c, "/api/ordenes", '{"tipo":"COMPRA","monto":500}')
    r = post(c, "/api/asistente", '{"mensaje":"¿tengo órdenes pendientes?"}')
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert list(cuerpo) == ["intencion", "respuesta", "accion", "sugerencias"]
    assert cuerpo["intencion"] == "ordenes" and "1 orden espera" in cuerpo["respuesta"]
    assert cuerpo["accion"] == {"tipo": "IR", "etiqueta": "Ir a Órdenes", "ruta": "/ordenes"}
    assert len(cuerpo["sugerencias"]) >= 2


def test_pedir_encenderlo_no_lo_enciende(app: FastAPI) -> None:
    c = registrado(app)
    r = post(c, "/api/asistente", '{"mensaje":"enciende el bot"}').json()
    assert r["accion"]["tipo"] == "INICIAR_BOT"
    assert c.get("/api/bot/estado").json()["activo"] is False


def test_sin_precio_igual_responde(app: FastAPI, fuente: FuenteFalsa) -> None:
    c = registrado(app)
    fuente.error = MercadoError("Binance no responde")
    r = post(c, "/api/asistente", '{"mensaje":"¿cuánto he ganado?"}')
    assert r.status_code == 200 and "no pude leer el precio" in r.json()["respuesta"]


@pytest.mark.parametrize(("cuerpo", "fragmento"), [
    ('{"mensaje":"   "}', "Escribe un mensaje"),
    ('{}', "Escribe un mensaje"),
    ('{"mensaje":"' + "a" * 301 + '"}', "demasiado largo"),
    ('{"mensaje":5}', ""),
])
def test_mensajes_invalidos(app: FastAPI, cuerpo: str, fragmento: str) -> None:
    r = post(registrado(app), "/api/asistente", cuerpo)
    assert r.status_code == 400 and fragmento in r.json()["error"]
