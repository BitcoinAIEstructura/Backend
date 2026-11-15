"""GET /api/buscar: el parámetro ``limite`` se valida antes de buscar.

Un ``limite`` que no es número no debe reventar con un 500: se trata como 0 y cae en la
misma validación de rango que ``0`` o ``21``, con un mensaje que dice cómo corregirlo.
"""

import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from tests.apoyo.fuente_falsa import FuenteFalsa


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(crear_app(Configuracion(), FuenteFalsa()))


@pytest.mark.parametrize("limite", ["abc", "1.5", "", " ", "muchos"])
def test_un_limite_que_no_es_numero_da_400(cliente: TestClient, limite: str) -> None:
    r = cliente.get("/api/buscar", params={"q": "rsi", "limite": limite})
    if limite.strip():
        assert r.status_code == 400
        assert "Parámetro 'limite' inválido" in r.json()["error"]


@pytest.mark.parametrize("limite", ["0", "-1", "21", "999"])
def test_un_limite_fuera_de_rango_da_400(cliente: TestClient, limite: str) -> None:
    r = cliente.get("/api/buscar", params={"q": "rsi", "limite": limite})
    assert r.status_code == 400
    assert "entre 1 y 20" in r.json()["error"]


def test_sin_limite_usa_el_valor_por_defecto(cliente: TestClient) -> None:
    r = cliente.get("/api/buscar", params={"q": "rsi"})
    assert r.status_code == 200
    assert r.json()["consulta"] == "rsi"


def test_con_limite_valido_busca(cliente: TestClient) -> None:
    r = cliente.get("/api/buscar", params={"q": "rsi", "limite": "3"})
    assert r.status_code == 200
    assert len(r.json()["resultados"]) <= 3


def test_una_consulta_demasiado_larga_da_400(cliente: TestClient) -> None:
    r = cliente.get("/api/buscar", params={"q": "x" * 200})
    assert r.status_code == 400
    assert "demasiado larga" in r.json()["error"]
