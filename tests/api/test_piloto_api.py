"""GET /api/estadisticas, GET /api/ia/consejo y el bot en modo "ia", con una FuenteFalsa a precio 100."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.simulacion import ConsejoPiloto, GestorSimulaciones, LimitesPiloto
from tests.api.test_simulacion_api import post, registrado
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import crear_entorno


class PilotoFalso:
    def __init__(self, senal: str = "COMPRAR") -> None:
        self.senal = senal

    def aconsejar(self, intervalo: str, limites: LimitesPiloto) -> ConsejoPiloto:
        return ConsejoPiloto(self.senal, 0.68, 0.36, 0.55, 0.5, 0.12, 0.015, 0.03, 0.005, "1h", 0, 100.0,
                             "El comité da 68 % de que sube.")


@pytest.fixture
def piloto() -> PilotoFalso:
    return PilotoFalso()


@pytest.fixture
def gestor(piloto: PilotoFalso) -> Iterator[GestorSimulaciones]:
    g = GestorSimulaciones(FuenteFalsa(), "BTCUSDT", piloto=piloto)
    yield g
    g.detener_todos()


@pytest.fixture
def app(gestor: GestorSimulaciones) -> FastAPI:
    return crear_app(Configuracion(), FuenteFalsa(), cuentas=crear_entorno().servicio, gestor=gestor)


@pytest.fixture
def cliente(app: FastAPI) -> TestClient:
    return registrado(app)


def test_estadisticas_con_operaciones(cliente: TestClient) -> None:
    vacia = cliente.get("/api/estadisticas").json()
    assert vacia["resumen"]["cerradas"] == 0 and vacia["resumen"]["tasaAcierto"] is None
    assert len(vacia["actividad"]) == 30 and vacia["reparto"] == {"usdt": 10_000, "btc": 0}
    post(cliente, "/api/ordenes", '{"tipo":"COMPRA","monto":1000}')
    post(cliente, "/api/ordenes/procesar")
    post(cliente, "/api/ordenes", '{"tipo":"VENTA","todo":true}')
    post(cliente, "/api/ordenes/procesar")
    e = cliente.get("/api/estadisticas").json()
    assert e["resumen"]["cerradas"] == 1 and e["resumen"]["perdedoras"] == 1  # solo pagó comisiones
    assert e["operaciones"][0]["origen"] == "manual" and e["operaciones"][0]["ganancia"] < 0
    assert {o["origen"]: o["ordenes"] for o in e["porOrigen"]} == {"manual": 2, "bot": 0, "ia": 0}
    assert e["actividad"][-1]["compras"] == 1 and e["actividad"][-1]["ventas"] == 1


def test_consejo_segun_la_cartera(cliente: TestClient, piloto: PilotoFalso) -> None:
    r = cliente.get("/api/ia/consejo")
    assert r.status_code == 200, r.text
    c = r.json()
    assert (c["accion"], c["titulo"]) == ("COMPRAR", "La IA recomienda comprar")
    assert c["decision"]["riesgo"] == 0.12 and "asesoría" in c["aviso"]
    piloto.senal = "VENDER"
    assert cliente.get("/api/ia/consejo").json()["accion"] == "ESPERAR"  # sin BTC no hay nada que vender


def test_bot_en_modo_ia(cliente: TestClient) -> None:
    estado = cliente.get("/api/bot/estado").json()
    assert estado["pilotoDisponible"] is True and estado["piloto"] is None
    r = post(cliente, "/api/bot/iniciar", '{"modo":"ia","segundosEntreCiclos":86400}')
    assert r.status_code == 200, r.text
    assert r.json()["configuracion"]["modo"] == "ia" and r.json()["estrategia"] == "piloto-ia"
    post(cliente, "/api/bot/detener")
    malo = post(cliente, "/api/bot/iniciar", '{"modo":"magia"}')
    assert malo.status_code == 400 and "modo" in malo.json()["error"]


def test_sin_sesion_y_sin_piloto(app: FastAPI) -> None:
    assert TestClient(app).get("/api/ia/consejo").status_code == 401
    sin = crear_app(Configuracion(), FuenteFalsa(), cuentas=crear_entorno().servicio,
                    gestor=GestorSimulaciones(FuenteFalsa(), "BTCUSDT"))
    assert registrado(sin).get("/api/ia/consejo").status_code == 503
