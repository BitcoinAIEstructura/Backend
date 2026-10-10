"""Pruebas de GET /api/indicadores con una FuenteFalsa (velas siempre crecientes)."""

import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.mercado import MercadoError
from tests.apoyo.fuente_falsa import FuenteFalsa


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa()


@pytest.fixture
def cliente(fuente: FuenteFalsa) -> TestClient:
    return TestClient(crear_app(Configuracion(), fuente))


def assert_400(cliente: TestClient, consulta: str, fragmento: str) -> None:
    r = cliente.get("/api/indicadores" + consulta)
    assert r.status_code == 400, r.text
    assert fragmento in r.json()["error"]


def test_rsi_devuelve_la_serie_y_las_velas_usadas(cliente: TestClient) -> None:
    r = cliente.get("/api/indicadores?indicador=rsi&periodo=14&intervalo=1d&cantidad=200")
    assert r.status_code == 200
    cuerpo = r.json()
    assert list(cuerpo) == ["simbolo", "intervalo", "indicador", "parametros", "series", "maximaCaida",
                            "cantidad", "velas"]
    assert cuerpo["indicador"] == "rsi"
    assert cuerpo["parametros"] == {"periodo": 14}
    assert len(cuerpo["velas"]) == 200
    valores = cuerpo["series"]["valor"]
    assert len(valores) == 186  # 200 − 14 de calentamiento
    assert valores[-1]["valor"] == 100  # la FuenteFalsa siempre sube
    assert valores[-1]["tiempo"] == cuerpo["velas"][-1]["tiempoApertura"]


def test_rsi_sin_periodo_usa_catorce(cliente: TestClient) -> None:
    cuerpo = cliente.get("/api/indicadores?indicador=rsi&cantidad=50").json()
    assert cuerpo["parametros"] == {"periodo": 14}
    assert len(cuerpo["series"]["valor"]) == 36


def test_macd_y_bollinger_devuelven_tres_series(cliente: TestClient) -> None:
    macd = cliente.get("/api/indicadores?indicador=macd&cantidad=100").json()
    assert list(macd["series"]) == ["macd", "senal", "histograma"]
    assert macd["parametros"] == {"rapido": 12, "lento": 26, "senal": 9}
    bollinger = cliente.get("/api/indicadores?indicador=bollinger&periodo=10&desviaciones=1.5").json()
    assert list(bollinger["series"]) == ["media", "superior", "inferior"]
    assert bollinger["parametros"] == {"periodo": 10, "desviaciones": 1.5}


@pytest.mark.parametrize("nombre", ["sma", "ema", "rsi", "macd", "bollinger", "volatilidad"])
def test_cada_indicador_de_la_fabrica_responde_200(cliente: TestClient, nombre: str) -> None:
    assert cliente.get(f"/api/indicadores?indicador={nombre}&cantidad=60").status_code == 200


def test_incluye_la_maxima_caida_de_las_velas(cliente: TestClient) -> None:
    caida = cliente.get("/api/indicadores?indicador=sma").json()["maximaCaida"]
    assert list(caida) == ["caidaMaxima", "tiempoPico", "valorPico", "tiempoValle", "valorValle"]
    assert caida["caidaMaxima"] == 0  # la FuenteFalsa nunca baja


def test_periodo_mayor_que_las_velas_devuelve_serie_vacia(cliente: TestClient) -> None:
    cuerpo = cliente.get("/api/indicadores?indicador=sma&periodo=500&cantidad=10").json()
    assert cuerpo["series"]["valor"] == []
    assert len(cuerpo["velas"]) == 10


def test_parametros_invalidos_dan_400_con_el_motivo_sin_consultar_la_fuente(cliente: TestClient,
                                                                           fuente: FuenteFalsa) -> None:
    assert_400(cliente, "", "Falta el parámetro 'indicador'")
    assert_400(cliente, "?indicador=adx", "Indicador desconocido")
    assert_400(cliente, "?indicador=rsi&periodo=1", "entre 2 y 1000")
    assert_400(cliente, "?indicador=rsi&periodo=abc", "'periodo' inválido")
    assert_400(cliente, "?indicador=macd&rapido=30&lento=20", "'lento'")
    assert_400(cliente, "?indicador=rsi&intervalo=2h", "'intervalo' inválido")
    assert_400(cliente, "?indicador=rsi&cantidad=0", "'cantidad' inválido")
    assert fuente.llamadas_velas == 0


def test_si_la_fuente_falla_responde_502(cliente: TestClient, fuente: FuenteFalsa) -> None:
    fuente.error = MercadoError("caída")
    r = cliente.get("/api/indicadores?indicador=rsi")
    assert r.status_code == 502
    assert r.text == '{"error":"Fuente de mercado no disponible"}'
