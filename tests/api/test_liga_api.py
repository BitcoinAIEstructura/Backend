"""GET /api/liga con la base en memoria: las carteras se guardan de verdad y la liga las lee."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.persistencia import AlmacenBaseDatos, participantes_activos
from bitcoinai.simulacion import GestorSimulaciones
from bitcoinai.simulacion.ranking import alias_publico
from tests.api.test_simulacion_api import post, registrado
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import crear_entorno


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa(precio=100.0)


@pytest.fixture
def app(fuente: FuenteFalsa) -> Iterator[FastAPI]:
    entorno = crear_entorno()
    gestor = GestorSimulaciones(fuente, "BTCUSDT", crear_almacen=lambda u: AlmacenBaseDatos(entorno.bd, u))
    yield crear_app(Configuracion(), fuente, cuentas=entorno.servicio, gestor=gestor,
                    participantes=lambda precio: participantes_activos(entorno.bd, precio))
    gestor.detener_todos()


def comprar(cliente: TestClient, monto: int) -> None:
    assert post(cliente, "/api/ordenes", f'{{"tipo":"COMPRA","monto":{monto}}}').status_code == 201
    assert post(cliente, "/api/ordenes/procesar").json()["estado"] == "EJECUTADA"


def test_la_liga_exige_sesion(app: FastAPI) -> None:
    assert TestClient(app).get("/api/liga").status_code == 401


def test_solo_entran_los_que_operaron_y_nadie_sale_con_su_nombre(app: FastAPI, fuente: FuenteFalsa) -> None:
    ana = registrado(app)
    beto = registrado(app, "beto@correo.co", "1098765432")
    carla = registrado(app, "carla@correo.co", "1011121314")
    comprar(ana, 1000)
    comprar(beto, 5000)
    fuente.precio = 120.0  # el BTC sube un 20 %: le va mejor a quien compró más

    liga = beto.get("/api/liga").json()
    assert liga["participantes"] == 2
    assert [m["posicion"] for m in liga["mejores"]] == [1, 2]
    primero, segundo = liga["mejores"]
    assert primero["esTuyo"] and not segundo["esTuyo"]
    assert primero["rentabilidad"] == pytest.approx((5000 + 4995 * 1.2 - 10_000) / 10_000)
    assert list(primero) == ["posicion", "alias", "rentabilidad", "valorTotal", "esTuyo"]
    assert liga["tu"]["posicion"] == 1
    assert "Ana" not in str(liga) and "Pérez" not in str(liga)
    assert primero["alias"] == alias_publico(2)

    # Carla no operó: ve la liga, pero ella no está.
    assert carla.get("/api/liga").json()["tu"] is None
