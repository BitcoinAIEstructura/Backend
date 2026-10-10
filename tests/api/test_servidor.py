"""Pruebas de punta a punta de la API con TestClient y una FuenteFalsa."""

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.mercado import MercadoError
from tests.apoyo.fuente_falsa import FuenteFalsa

ORIGEN = "https://panel.ejemplo.com"
JSON = "application/json; charset=utf-8"


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa()


@pytest.fixture
def cliente(fuente: FuenteFalsa) -> TestClient:
    return TestClient(crear_app(Configuracion(origen_permitido=ORIGEN), fuente))


def assert_error(respuesta: httpx.Response, codigo: int, fragmento: str) -> None:
    assert respuesta.status_code == codigo, respuesta.text
    assert respuesta.headers["content-type"] == JSON
    cuerpo = respuesta.json()
    assert list(cuerpo) == ["error"], "solo debe venir el campo error"
    assert fragmento in cuerpo["error"]


# ---------- respuestas correctas ----------


def test_health_responde_ok_sin_consultar_la_fuente(cliente: TestClient, fuente: FuenteFalsa) -> None:
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.headers["content-type"] == JSON
    assert r.text == '{"estado":"ok"}'
    assert fuente.llamadas_velas + fuente.llamadas_precio == 0


def test_health_con_barra_final_tambien_funciona_sin_redirigir(cliente: TestClient) -> None:
    r = cliente.get("/health/", follow_redirects=False)
    assert r.status_code == 200
    assert r.json() == {"estado": "ok"}


def test_precio_devuelve_simbolo_precio_y_momento(cliente: TestClient, fuente: FuenteFalsa) -> None:
    fuente.precio = 67123.45
    antes = int(time.time() * 1000)
    r = cliente.get("/api/precio")
    assert r.status_code == 200
    cuerpo = r.json()
    assert list(cuerpo) == ["simbolo", "precio", "momento"]
    assert cuerpo["simbolo"] == "BTCUSDT"
    assert cuerpo["precio"] == 67123.45
    assert cuerpo["momento"] >= antes


def test_velas_con_parametros(cliente: TestClient) -> None:
    r = cliente.get("/api/velas?intervalo=1d&cantidad=5")
    assert r.status_code == 200
    assert r.headers["content-type"] == JSON
    cuerpo = r.json()
    assert list(cuerpo) == ["simbolo", "intervalo", "cantidad", "velas"]
    assert cuerpo["simbolo"] == "BTCUSDT"
    assert cuerpo["intervalo"] == "1d"
    assert cuerpo["cantidad"] == 5
    assert len(cuerpo["velas"]) == 5
    ultima = cuerpo["velas"][-1]
    assert ultima["apertura"] == 599  # FuenteFalsa: la vela 499 abre en 100 + 499
    assert list(ultima) == ["tiempoApertura", "apertura", "maximo", "minimo", "cierre", "volumen", "tiempoCierre"]


def test_velas_sin_parametros_usa_los_valores_por_defecto(cliente: TestClient) -> None:
    cuerpo = cliente.get("/api/velas").json()
    assert cuerpo["intervalo"] == "1d"
    assert cuerpo["cantidad"] == 200
    assert cliente.get("/api/velas?cantidad=&intervalo=").json()["cantidad"] == 200


def test_velas_acepta_los_limites_de_cantidad(cliente: TestClient) -> None:
    assert len(cliente.get("/api/velas?cantidad=1").json()["velas"]) == 1
    assert cliente.get("/api/velas?cantidad=1000&intervalo=4h").status_code == 200


# ---------- parámetros inválidos ----------


def test_intervalo_invalido_da_400_con_el_motivo(cliente: TestClient) -> None:
    assert_error(cliente.get("/api/velas?intervalo=2h"), 400,
                 "Parámetro 'intervalo' inválido: '2h'. Valores permitidos: 1m, 5m, 15m, 1h, 4h, 1d")
    assert_error(cliente.get("/api/velas?intervalo=1D"), 400, "1m, 5m, 15m, 1h, 4h, 1d")


@pytest.mark.parametrize("cantidad", ["0", "1001", "abc", "2.5", "-3"])
def test_cantidad_invalida_da_400_con_el_motivo(cliente: TestClient, fuente: FuenteFalsa, cantidad: str) -> None:
    assert_error(cliente.get(f"/api/velas?cantidad={cantidad}"), 400,
                 f"Parámetro 'cantidad' inválido: '{cantidad}'. Debe ser un número entero entre 1 y 1000")
    assert fuente.llamadas_velas == 0


# ---------- rutas y métodos ----------


def test_ruta_inexistente_da_404_en_json(cliente: TestClient) -> None:
    assert_error(cliente.get("/api/no-existe"), 404, "Ruta no encontrada: /api/no-existe")
    assert_error(cliente.get("/"), 404, "Ruta no encontrada: /")


def test_metodo_no_permitido_da_405_con_encabezado_allow(cliente: TestClient) -> None:
    r = cliente.post("/health")
    assert_error(r, 405, "Método POST no permitido en /health; use GET")
    assert r.headers["allow"] == "GET"
    assert_error(cliente.delete("/api/velas"), 405, "no permitido")


def test_la_documentacion_interactiva_esta_en_docs(cliente: TestClient) -> None:
    assert cliente.get("/docs").status_code == 200
    assert "/api/velas" in cliente.get("/openapi.json").json()["paths"]


# ---------- CORS ----------


def test_las_respuestas_llevan_encabezados_cors(cliente: TestClient) -> None:
    r = cliente.get("/health")
    assert r.headers["access-control-allow-origin"] == ORIGEN
    assert r.headers["vary"] == "Origin"
    error = cliente.get("/nada")
    assert error.headers["access-control-allow-origin"] == ORIGEN


def test_options_responde_preflight_sin_llegar_al_manejador(cliente: TestClient, fuente: FuenteFalsa) -> None:
    r = cliente.options("/api/velas")
    assert r.status_code == 204
    assert r.headers["access-control-allow-origin"] == ORIGEN
    assert "GET" in r.headers["access-control-allow-methods"]
    assert "Content-Type" in r.headers["access-control-allow-headers"]
    assert r.text == ""
    assert fuente.llamadas_velas == 0


def test_origen_comodin_por_defecto(fuente: FuenteFalsa) -> None:
    r = TestClient(crear_app(Configuracion(), fuente)).get("/health")
    assert r.headers["access-control-allow-origin"] == "*"
    assert "vary" not in r.headers


# ---------- fallos ----------


def test_si_la_fuente_falla_responde_502_sin_detalles_internos(cliente: TestClient, fuente: FuenteFalsa) -> None:
    fuente.error = MercadoError("Binance respondió HTTP 451: detalle interno")
    velas = cliente.get("/api/velas?cantidad=5")
    assert_error(velas, 502, "Fuente de mercado no disponible")
    assert velas.text == '{"error":"Fuente de mercado no disponible"}'
    assert_error(cliente.get("/api/precio"), 502, "Fuente de mercado no disponible")
    assert cliente.get("/health").status_code == 200


def test_error_inesperado_responde_500_sin_traza(cliente: TestClient, fuente: FuenteFalsa) -> None:
    fuente.error = RuntimeError("secreto interno")
    r = cliente.get("/api/precio")
    assert_error(r, 500, "Error interno del servidor")
    assert "secreto" not in r.text
    assert "Error" not in r.text.replace("Error interno", "")
    assert r.headers["access-control-allow-origin"] == ORIGEN  # el 500 también lleva CORS


def test_validacion_de_fastapi_da_400_en_json(fuente: FuenteFalsa) -> None:
    app = crear_app(Configuracion(), fuente)

    @app.get("/prueba")
    def prueba(numero: int) -> dict[str, int]:
        return {"numero": numero}

    r = TestClient(app).get("/prueba?numero=abc")
    assert_error(r, 400, "El campo 'numero' debe ser un número entero")
