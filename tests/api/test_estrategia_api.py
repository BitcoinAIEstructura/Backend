"""Pruebas de /api/senal y /api/backtest con una FuenteFalsa de 500 velas que siempre suben."""

import time

import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.estrategia import AVISO
from bitcoinai.mercado import MercadoError
from bitcoinai.modelo import Intervalo, Vela
from tests.apoyo.fuente_falsa import FuenteFalsa, generar_velas


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa()


@pytest.fixture
def cliente(fuente: FuenteFalsa) -> TestClient:
    return TestClient(crear_app(Configuracion(), fuente))


def assert_400(cliente: TestClient, ruta: str, fragmento: str) -> None:
    r = cliente.get(ruta)
    assert r.status_code == 400, r.text
    assert fragmento in r.json()["error"]


# ---------- /api/senal ----------


def test_senal_por_defecto_es_la_combinada_con_decision_y_pronostico(cliente: TestClient) -> None:
    r = cliente.get("/api/senal")
    assert r.status_code == 200
    cuerpo = r.json()
    assert list(cuerpo) == ["simbolo", "intervalo", "estrategia", "parametros", "velasAnalizadas", "decision",
                            "pronostico"]
    assert cuerpo["estrategia"] == "combinada"
    assert cuerpo["velasAnalizadas"] == 200
    assert list(cuerpo["decision"]) == ["tiempo", "senal", "precio", "confianza", "motivo"]
    assert cuerpo["decision"]["precio"] == 600  # cierre de la última vela de la FuenteFalsa
    assert list(cuerpo["pronostico"]) == ["direccion", "confianza", "justificacion", "indicadores", "aviso"]
    assert cuerpo["pronostico"]["aviso"] == AVISO
    assert len(cuerpo["pronostico"]["indicadores"]) == 6


def test_senal_de_una_estrategia_con_sus_parametros(cliente: TestClient) -> None:
    cuerpo = cliente.get("/api/senal?estrategia=rsi&periodo=7&intervalo=4h&cantidad=50").json()
    assert (cuerpo["estrategia"], cuerpo["intervalo"]) == ("rsi", "4h")
    assert cuerpo["parametros"] == {"periodo": 7, "sobreventa": 30.0, "sobrecompra": 70.0}
    # La FuenteFalsa siempre sube: RSI 100, en sobrecompra, sin señal de giro.
    assert cuerpo["decision"]["senal"] == "MANTENER"
    assert cuerpo["pronostico"]["direccion"] == "LATERAL"


def test_la_vela_que_todavia_no_cierra_se_descarta(cliente: TestClient, fuente: FuenteFalsa) -> None:
    velas = generar_velas(60, Intervalo.D1)
    ahora = int(time.time() * 1000)
    velas.agregar_final(Vela(ahora - 1000, 700, 710, 690, 705, 1, ahora + Intervalo.D1.milisegundos))
    fuente.velas = velas
    cuerpo = cliente.get("/api/senal?estrategia=cruce&cantidad=100").json()
    assert cuerpo["velasAnalizadas"] == 60
    assert cuerpo["decision"]["precio"] == 160  # cierre de la vela 59, no 705


def test_senal_con_parametros_invalidos_da_400(cliente: TestClient, fuente: FuenteFalsa) -> None:
    assert_400(cliente, "/api/senal?estrategia=magia", "Estrategia desconocida")
    assert_400(cliente, "/api/senal?estrategia=cruce&corta=50&larga=20", "'larga'")
    assert_400(cliente, "/api/senal?intervalo=7m", "'intervalo'")
    assert fuente.llamadas_velas == 0


# ---------- /api/backtest ----------


def test_backtest_devuelve_resultado_validacion_y_aviso(cliente: TestClient) -> None:
    r = cliente.get("/api/backtest?estrategia=cruce&capital=1000&comision=0.001&intervalo=1d&cantidad=1000")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert list(cuerpo) == ["simbolo", "intervalo", "estrategia", "parametros", "resultado", "validacion", "aviso"]
    assert cuerpo["aviso"] == AVISO
    resultado = cuerpo["resultado"]
    assert resultado["capitalInicial"] == 1000
    assert resultado["velasAnalizadas"] == 500  # la FuenteFalsa tiene 500
    # primera apertura 100, último cierre 600, comisión en compra y venta
    assert resultado["rentabilidadComprarYMantener"] == pytest.approx(0.999 * 0.999 * 6 - 1)
    assert "curvaCapital" in resultado and "operaciones" in resultado
    validacion = cuerpo["validacion"]
    assert (validacion["velasEntrenamiento"], validacion["velasPrueba"]) == (350, 150)
    assert len(validacion["candidatos"]) == 9
    assert validacion["prueba"]["velasAnalizadas"] == 150


def test_backtest_por_defecto_usa_la_combinada_y_setenta_por_ciento(cliente: TestClient) -> None:
    cuerpo = cliente.get("/api/backtest?cantidad=300").json()
    assert cuerpo["estrategia"] == "combinada"
    assert cuerpo["validacion"]["fraccionEntrenamiento"] == 0.7
    assert cuerpo["validacion"]["velasEntrenamiento"] == 210
    assert len(cuerpo["validacion"]["candidatos"]) == 4


@pytest.mark.parametrize(("consulta", "fragmento"), [
    ("capital=0", "'capital'"), ("capital=abc", "'capital'"), ("comision=0.1", "'comision'"),
    ("entrenamiento=0.95", "'entrenamiento'"), ("cantidad=5000", "'cantidad'"),
    ("estrategia=macd&lento=5&rapido=10", "'lento'"),
])
def test_backtest_con_parametros_invalidos_da_400(cliente: TestClient, fuente: FuenteFalsa, consulta: str,
                                                   fragmento: str) -> None:
    assert_400(cliente, f"/api/backtest?{consulta}", fragmento)
    assert fuente.llamadas_velas == 0


def test_si_la_fuente_falla_responde_502(cliente: TestClient, fuente: FuenteFalsa) -> None:
    fuente.error = MercadoError("caída")
    assert cliente.get("/api/backtest?estrategia=cruce").status_code == 502
    assert cliente.get("/api/senal").status_code == 502
