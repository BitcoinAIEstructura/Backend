"""GET /api/estructuras (con sesión) y POST /api/estructuras/demo (pública)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.api.test_simulacion_api import app, fuente, gestor, post, registrado  # noqa: F401 (fixtures)


def test_demo_corre_el_codigo_real(app: FastAPI) -> None:  # noqa: F811
    r = TestClient(app).post("/api/estructuras/demo", json={
        "estructura": "avl",
        "operaciones": [{"operacion": "insertar", "valor": v} for v in (10, 20, 30)],
    })
    assert r.status_code == 200, r.text
    pasos = r.json()["pasos"]
    assert len(pasos) == 3
    assert "Rotación simple a la izquierda en 10" in pasos[2]["descripcion"]
    assert pasos[2]["estado"]["raiz"]["clave"] == 20


@pytest.mark.parametrize("cuerpo", [
    {"estructura": "lista", "operaciones": []},
    {"estructura": "pila", "operaciones": [{"operacion": "apilar", "valor": "7"}]},
    {"estructura": "pila"},
])
def test_demo_invalida_da_400(app: FastAPI, cuerpo: dict[str, object]) -> None:  # noqa: F811
    r = TestClient(app).post("/api/estructuras/demo", json=cuerpo)
    assert r.status_code == 400, r.text


def test_estructuras_exige_sesion(app: FastAPI) -> None:  # noqa: F811
    assert TestClient(app).get("/api/estructuras").status_code == 401


def test_foto_de_las_estructuras_reales_sin_cambiarlas(app: FastAPI) -> None:  # noqa: F811
    cliente = registrado(app)
    for monto in (10, 20, 30):
        post(cliente, "/api/ordenes", f'{{"tipo":"COMPRA","monto":{monto}}}')
    post(cliente, "/api/ordenes/procesar")
    cliente.get("/api/precio")

    antes = cliente.get("/api/ordenes").json()
    foto = cliente.get("/api/estructuras").json()
    assert foto["cola"]["tamanio"] == 2
    assert [o["id"] for o in foto["cola"]["ordenes"]] == [2, 3]
    assert foto["pila"]["tamanio"] == 4 and foto["pila"]["eventos"][0]["tipo"] == "ORDEN_EJECUTADA"
    assert foto["pilaDeshacer"] == {"tamanio": 3, "ids": [3, 2, 1]}
    assert foto["lista"]["tamanio"] == 1
    assert foto["tablaHash"]["tamanio"] == 1 and sum(foto["tablaHash"]["longitudes"]) == 1
    assert foto["colaCircular"]["tamanio"] == 1 and foto["colaCircular"]["capacidad"] == 120
    assert foto["trie"]["nodos"] > foto["trie"]["palabras"] > 0
    assert cliente.get("/api/ordenes").json() == antes  # leer no cambió nada
