"""GET /api/ia/predicciones con la FuenteFalsa (500 velas diarias que siempre suben)."""

import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.api.rutas_ia import _nodo
from bitcoinai.ia.arbol import ArbolDecision
from bitcoinai.ia.caracteristicas import NOMBRES
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.ia.apoyo import separables, vector


@pytest.fixture(scope="module")
def cliente() -> TestClient:
    return TestClient(crear_app(Configuracion(), FuenteFalsa()))


def test_predicciones_con_metricas_y_explicaciones(cliente: TestClient) -> None:
    r = cliente.get("/api/ia/predicciones", params={"intervalo": "1d"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["intervalo"], p["muestrasEntrenamiento"], p["muestrasPrueba"]) == ("1d", 359, 90)
    assert [m["nombre"] for m in p["modelos"]] == ["Regresión logística", "Árbol de decisión", "k vecinos"]
    comite = p["comite"]
    assert comite["nombre"] == "Comité" and comite["peso"] is None
    assert set(comite["metricas"]) == {"muestras", "exactitud", "base", "ventaja", "precisionSube", "vecesDijoSube"}
    assert comite["direccion"] == "SUBE"  # en estos datos siempre sube
    assert len(p["caracteristicas"]) == 10 and p["caracteristicas"][3]["nombre"] == "RSI 14"
    assert len(p["prueba"]) == 90
    assert p["arbol"]["enCamino"] is True
    assert "No es asesoría financiera" in p["aviso"]
    # Los textos de la página salen de aquí: el frontend solo los muestra.
    assert p["nombreIntervalo"] == "1 día" and p["intervalos"][0] == {"codigo": "15m", "nombre": "15 min"}
    assert p["encabezado"]["etiqueta"] == "Hecho a mano"
    arbol = p["modelos"][1]
    assert arbol["descripcion"]["factoresConSigno"] is False and "sí/no" in arbol["descripcion"]["idea"]
    veredicto = comite["veredicto"]
    assert veredicto["gana"] == (comite["metricas"]["ventaja"] > 0)
    assert str(comite["metricas"]["muestras"]) in veredicto["texto"]
    assert p["fuentesExternas"] == {"usadas": [], "omitidas": [], "comparacion": None}


def test_la_segunda_peticion_sale_de_la_cache(cliente: TestClient) -> None:
    primera = cliente.get("/api/ia/predicciones", params={"intervalo": "1d"}).json()
    segunda = cliente.get("/api/ia/predicciones", params={"intervalo": "1d"}).json()
    assert primera["entrenadoEn"] == segunda["entrenadoEn"]


def test_intervalo_invalido(cliente: TestClient) -> None:
    r = cliente.get("/api/ia/predicciones", params={"intervalo": "1m"})
    assert r.status_code == 400 and "15m, 1h, 4h, 1d" in r.json()["error"]


def test_el_arbol_marca_el_camino_de_la_vela_de_ahora() -> None:
    arbol = ArbolDecision()
    arbol.entrenar(separables())
    forma = _nodo(arbol.raiz, vector(20), NOMBRES, True)
    assert forma is not None and forma["caracteristica"] == "RSI 14"
    assert forma["si"]["enCamino"] is True and forma["no"]["enCamino"] is False
