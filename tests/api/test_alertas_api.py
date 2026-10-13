"""/api/alertas con la base en memoria; la FuenteFalsa está a precio 100."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.alertas.servicio import ServicioAlertas
from bitcoinai.api import Configuracion, crear_app
from tests.api.test_simulacion_api import post, registrado
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import Entorno, crear_entorno


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa(precio=100.0)


@pytest.fixture
def entorno() -> Entorno:
    return crear_entorno()


@pytest.fixture
def servicio(fuente: FuenteFalsa, entorno: Entorno) -> ServicioAlertas:
    return ServicioAlertas(entorno.bd, fuente, "BTCUSDT")


@pytest.fixture
def app(fuente: FuenteFalsa, entorno: Entorno, servicio: ServicioAlertas) -> Iterator[FastAPI]:
    yield crear_app(Configuracion(), fuente, cuentas=entorno.servicio, alertas=servicio)


def test_exige_sesion(app: FastAPI) -> None:
    assert TestClient(app).get("/api/alertas").status_code == 401


def test_crear_listar_disparar_y_cancelar(app: FastAPI, servicio: ServicioAlertas) -> None:
    c = registrado(app)
    r = post(c, "/api/alertas", '{"tipo":"SUBE_A","precio":110}')
    assert r.status_code == 201, r.text
    sube = r.json()
    assert list(sube) == ["id", "tipo", "precio", "estado", "creadaEn", "disparadaEn", "precioDisparo"]
    baja = post(c, "/api/alertas", '{"tipo":"BAJA_A","precio":90}').json()

    servicio.revisar(111)
    lista = c.get("/api/alertas").json()
    assert lista["activas"] == 1
    estados = {a["id"]: a["estado"] for a in lista["alertas"]}
    assert estados == {sube["id"]: "DISPARADA", baja["id"]: "ACTIVA"}

    assert c.delete(f"/api/alertas/{baja['id']}").status_code == 204
    assert c.delete(f"/api/alertas/{baja['id']}").status_code == 404
    assert c.delete("/api/alertas/abc").status_code == 404


def test_datos_invalidos(app: FastAPI) -> None:
    c = registrado(app)
    r = post(c, "/api/alertas", '{"tipo":"SUBE_A","precio":50}')
    assert r.status_code == 400 and "por encima del actual" in r.json()["error"]
    assert post(c, "/api/alertas", '{"tipo":"SUBE_A","precio":"mucho"}').status_code == 400


def test_nadie_ve_ni_cancela_las_alertas_de_otro(app: FastAPI) -> None:
    ana = registrado(app)
    beto = registrado(app, "beto@correo.co", "1098765432")
    alerta = post(ana, "/api/alertas", '{"tipo":"SUBE_A","precio":120}').json()
    assert beto.get("/api/alertas").json() == {"activas": 0, "alertas": []}
    assert beto.delete(f"/api/alertas/{alerta['id']}").status_code == 404
