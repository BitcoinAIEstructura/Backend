"""Pruebas de los endpoints de órdenes, cartera, historial y bot, con una FuenteFalsa a precio 100.

Cada cliente se registra primero: la simulación es de cada usuario y exige sesión.
"""

from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.mercado import MercadoError
from bitcoinai.simulacion import GestorSimulaciones
from tests.api.test_cuentas_api import REGISTRO
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


def registrado(app: FastAPI, correo: str = "ana@correo.co", documento: str = "1023456789") -> TestClient:
    c = TestClient(app)
    r = c.post("/api/cuentas/registro", json={**REGISTRO, "correo": correo, "numeroDocumento": documento})
    assert r.status_code == 201, r.text
    return c


@pytest.fixture
def cliente(app: FastAPI) -> TestClient:
    return registrado(app)


def post(cliente: TestClient, ruta: str, cuerpo: str | None = None) -> httpx.Response:
    return cliente.post(ruta, content=cuerpo, headers={"Content-Type": "application/json"} if cuerpo else {})


def assert_error(r: httpx.Response, codigo: int, fragmento: str) -> None:
    assert r.status_code == codigo, r.text
    assert fragmento in r.json()["error"], r.json()["error"]


# ---------- flujo completo ----------


def test_crear_procesar_y_ver_el_cambio_en_la_cartera(cliente: TestClient) -> None:
    creada = post(cliente, "/api/ordenes", '{"tipo":"COMPRA","monto":500}')
    assert creada.status_code == 201, creada.text
    orden = creada.json()
    assert (orden["id"], orden["estado"], orden["motivo"]) == (1, "PENDIENTE", "manual")
    assert list(orden) == ["id", "tipo", "monto", "todo", "estado", "creadaEn", "ejecutadaEn", "precioEjecucion",
                           "cantidadBtc", "comision", "motivo", "detalle"]

    procesada = post(cliente, "/api/ordenes/procesar")
    assert procesada.status_code == 200
    assert (procesada.json()["estado"], procesada.json()["precioEjecucion"]) == ("EJECUTADA", 100)

    cartera = cliente.get("/api/cartera").json()
    assert cartera["saldoUsdt"] == 9_500
    assert cartera["btc"] == pytest.approx(4.995)
    assert (cartera["precioActual"], cartera["saldoInicial"]) == (100, 10_000)


def test_venta_de_todo_por_api(cliente: TestClient) -> None:
    post(cliente, "/api/ordenes", '{"tipo":"COMPRA","monto":1000}')
    post(cliente, "/api/ordenes/procesar")
    assert post(cliente, "/api/ordenes", '{"tipo":"VENTA","todo":true,"motivo":"salir"}').status_code == 201
    assert post(cliente, "/api/ordenes/procesar").json()["motivo"] == "salir"
    assert cliente.get("/api/cartera").json()["btc"] == 0


def test_listar_filtrar_obtener_y_cancelar(cliente: TestClient) -> None:
    for cuerpo in ('{"tipo":"COMPRA","monto":100}', '{"tipo":"COMPRA","monto":200}', '{"tipo":"compra","monto":300}'):
        post(cliente, "/api/ordenes", cuerpo)
    cancelada = cliente.delete("/api/ordenes/2")
    assert (cancelada.status_code, cancelada.json()["estado"]) == (200, "CANCELADA")
    pendientes = cliente.get("/api/ordenes?estado=pendiente").json()
    assert pendientes["cantidad"] == 2
    assert [o["id"] for o in pendientes["ordenes"]] == [1, 3]
    assert cliente.get("/api/ordenes").json()["cantidad"] == 3
    assert cliente.get("/api/ordenes/2").json()["estado"] == "CANCELADA"


def test_deshacer_la_ultima_orden(cliente: TestClient) -> None:
    post(cliente, "/api/ordenes", '{"tipo":"COMPRA","monto":100}')
    post(cliente, "/api/ordenes", '{"tipo":"COMPRA","monto":200}')
    r = post(cliente, "/api/ordenes/deshacer")
    assert (r.status_code, r.json()["id"]) == (200, 2)
    assert cliente.get("/api/ordenes?estado=PENDIENTE").json()["cantidad"] == 1


def test_historial_con_limite(cliente: TestClient) -> None:
    post(cliente, "/api/ordenes", '{"tipo":"COMPRA","monto":100}')
    post(cliente, "/api/ordenes/procesar")
    eventos = cliente.get("/api/historial?limite=1").json()["eventos"]
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "ORDEN_EJECUTADA"
    assert list(eventos[0]) == ["momento", "tipo", "idOrden", "descripcion"]
    assert len(cliente.get("/api/historial").json()["eventos"]) == 2


# ---------- validación del cuerpo ----------


@pytest.mark.parametrize(("cuerpo", "fragmento"), [
    (None, "Falta el cuerpo JSON"),
    ("no es json", "Cuerpo JSON inválido"),
    ("[1,2]", "objeto JSON"),
    ('{"monto":500}', "Falta el campo 'tipo'"),
    ('{"tipo":"PRESTAMO","monto":500}', "COMPRA, VENTA"),
    ('{"tipo":"COMPRA"}', "Falta el campo 'monto'"),
    ('{"tipo":"COMPRA","monto":0}', "mayor que 0"),
    ('{"tipo":"COMPRA","monto":-5}', "mayor que 0"),
    ('{"tipo":"COMPRA","monto":"500"}', "debe ser un número"),
    ('{"tipo":"COMPRA","todo":true}', "solo se usa en órdenes de VENTA"),
    ('{"tipo":"VENTA","todo":true,"monto":5}', "no se indica 'monto'"),
    ('{"tipo":"VENTA","todo":"si"}', "'todo'"),
])
def test_cuerpos_invalidos_dan_400_con_el_motivo(cliente: TestClient, cuerpo: str | None, fragmento: str) -> None:
    assert_error(post(cliente, "/api/ordenes", cuerpo), 400, fragmento)
    assert cliente.get("/api/ordenes").json()["cantidad"] == 0


def test_errores_de_estado_y_de_id(cliente: TestClient) -> None:
    assert_error(post(cliente, "/api/ordenes/procesar"), 409, "No hay órdenes pendientes")
    assert_error(post(cliente, "/api/ordenes/deshacer"), 409, "No hay una orden")
    assert_error(cliente.delete("/api/ordenes/99"), 404, "No existe la orden #99")
    assert_error(cliente.get("/api/ordenes/99"), 404, "#99")
    assert_error(cliente.delete("/api/ordenes/abc"), 400, "Id de orden inválido")
    post(cliente, "/api/ordenes", '{"tipo":"COMPRA","monto":100}')
    post(cliente, "/api/ordenes/procesar")
    assert_error(cliente.delete("/api/ordenes/1"), 409, "ya no está pendiente")
    assert_error(cliente.get("/api/ordenes?estado=RARA"), 400, "'estado'")
    assert_error(cliente.get("/api/historial?limite=0"), 400, "'limite'")


def test_si_falla_el_precio_responde_502_y_la_orden_sigue_en_la_cola(cliente: TestClient,
                                                                    fuente: FuenteFalsa) -> None:
    post(cliente, "/api/ordenes", '{"tipo":"COMPRA","monto":100}')
    fuente.error = MercadoError("caída")
    assert post(cliente, "/api/ordenes/procesar").status_code == 502
    assert cliente.get("/api/cartera").status_code == 502
    fuente.error = None
    assert cliente.get("/api/ordenes/1").json()["estado"] == "PENDIENTE"


# ---------- bot ----------


def test_iniciar_consultar_y_detener_el_bot(cliente: TestClient) -> None:
    assert cliente.get("/api/bot/estado").json()["activo"] is False
    iniciado = post(cliente, "/api/bot/iniciar", '{"segundosEntreCiclos":3600,"riesgo":0.1,"intervalo":"1d"}')
    assert iniciado.status_code == 200, iniciado.text
    estado = iniciado.json()
    assert (estado["activo"], estado["estrategia"]) == (True, "combinada")
    configuracion = estado["configuracion"]
    assert (configuracion["segundosEntreCiclos"], configuracion["riesgo"], configuracion["intervalo"]) == (
        3600, 0.1, "1d")
    assert configuracion["stopLoss"] == 0.05  # por defecto
    assert_error(post(cliente, "/api/bot/iniciar"), 409, "ya está en marcha")
    assert post(cliente, "/api/bot/detener").json()["activo"] is False
    assert post(cliente, "/api/bot/detener").json()["activo"] is False


@pytest.mark.parametrize(("cuerpo", "fragmento"), [
    ('{"riesgo":2}', "'riesgo'"),
    ('{"intervalo":"2h"}', "Intervalo no soportado"),
    ('{"segundosEntreCiclos":1.5}', "entero"),
    ('{"stopLoss":"x"}', "'stopLoss'"),
])
def test_configuracion_del_bot_invalida_da_400(cliente: TestClient, cuerpo: str, fragmento: str) -> None:
    assert_error(post(cliente, "/api/bot/iniciar", cuerpo), 400, fragmento)
    assert cliente.get("/api/bot/estado").json()["activo"] is False


# ---------- cada usuario con lo suyo ----------


@pytest.mark.parametrize(("metodo", "ruta"), [
    ("GET", "/api/ordenes"), ("POST", "/api/ordenes"), ("GET", "/api/ordenes/1"), ("DELETE", "/api/ordenes/1"),
    ("POST", "/api/ordenes/procesar"), ("POST", "/api/ordenes/deshacer"), ("GET", "/api/cartera"),
    ("GET", "/api/historial"), ("POST", "/api/bot/iniciar"), ("POST", "/api/bot/detener"), ("GET", "/api/bot/estado"),
])
def test_sin_sesion_da_401(app: FastAPI, metodo: str, ruta: str) -> None:
    r = TestClient(app).request(metodo, ruta, json={"tipo": "COMPRA", "monto": 5} if metodo == "POST" else None)
    assert r.status_code == 401, r.text


def test_la_sesion_se_revisa_antes_que_el_cuerpo(app: FastAPI) -> None:
    assert TestClient(app).post("/api/ordenes", json={"tipo": "PRESTAMO"}).status_code == 401


def test_cada_usuario_ve_solo_lo_suyo(app: FastAPI) -> None:
    ana, luis = registrado(app), registrado(app, "luis@correo.co", "79123456")
    post(ana, "/api/ordenes", '{"tipo":"COMPRA","monto":1000}')
    post(ana, "/api/ordenes/procesar")
    assert ana.get("/api/cartera").json()["saldoUsdt"] == 9_000
    assert luis.get("/api/cartera").json()["saldoUsdt"] == 10_000
    assert luis.get("/api/ordenes").json()["cantidad"] == 0
    assert luis.get("/api/ordenes/1").status_code == 404  # la orden #1 de Ana no existe para Luis
    assert luis.delete("/api/ordenes/1").status_code == 404
    assert len(ana.get("/api/historial").json()["eventos"]) == 2
    assert luis.get("/api/historial").json()["eventos"] == []


def test_bots_independientes_y_con_limite(fuente: FuenteFalsa) -> None:
    gestor = GestorSimulaciones(fuente, "BTCUSDT", maximo_bots=1)
    app = crear_app(Configuracion(), fuente, cuentas=crear_entorno().servicio, gestor=gestor)
    ana, luis = registrado(app), registrado(app, "luis@correo.co", "79123456")
    try:
        assert post(ana, "/api/bot/iniciar", '{"segundosEntreCiclos":3600}').json()["activo"] is True
        assert luis.get("/api/bot/estado").json()["activo"] is False
        assert_error(post(luis, "/api/bot/iniciar", '{"segundosEntreCiclos":3600}'), 409, "demasiados bots")
    finally:
        gestor.detener_todos()
