from pathlib import Path

from fastapi.testclient import TestClient

from bitcoinai.__main__ import construir
from bitcoinai.api import Configuracion
from bitcoinai.api.publicador import Publicador
from bitcoinai.seguridad.claves import ARCHIVO_CLAVE
from bitcoinai.seguridad.contrasenas import PARAMETROS_RAPIDOS_PARA_PRUEBAS, HashContrasenas
from tests.api.test_cuentas_api import REGISTRO


def test_construir_arma_la_app_con_health_disponible_sin_consultar_binance(tmp_path: Path) -> None:
    app = construir(Configuracion(data_dir=str(tmp_path)))
    respuesta = TestClient(app).get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
    assert isinstance(app.state.publicador, Publicador)


def test_la_simulacion_sobrevive_a_un_reinicio(tmp_path: Path) -> None:
    config = Configuracion(data_dir=str(tmp_path))
    with TestClient(construir(config)) as cliente:
        assert cliente.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 100}).status_code == 201
        assert cliente.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 200}).status_code == 201
        assert cliente.delete("/api/ordenes/1").status_code == 200
    assert (tmp_path / "ordenes.json").exists()

    with TestClient(construir(config)) as cliente:  # "reinicio": app nueva, mismos archivos
        ordenes = cliente.get("/api/ordenes").json()["ordenes"]
        assert [(o["id"], o["estado"]) for o in ordenes] == [(2, "PENDIENTE"), (1, "CANCELADA")]
        assert cliente.get("/api/historial?limite=1").json()["eventos"][0]["tipo"] == "ORDEN_CANCELADA"
        assert cliente.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 5}).json()["id"] == 3


def test_las_cuentas_sobreviven_a_un_reinicio(tmp_path: Path) -> None:
    config = Configuracion(data_dir=str(tmp_path))
    hasher = HashContrasenas(PARAMETROS_RAPIDOS_PARA_PRUEBAS)
    with TestClient(construir(config, hasher)) as cliente:
        assert cliente.post("/api/cuentas/registro", json=REGISTRO).status_code == 201
    assert (tmp_path / "bitcoinai.db").exists() and (tmp_path / ARCHIVO_CLAVE).exists()
    with TestClient(construir(config, hasher)) as cliente:  # misma base y misma clave
        r = cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": REGISTRO["contrasena"]})
        assert r.status_code == 200
        assert r.json()["usuario"]["documento"] == "******6789"  # se descifra con la clave guardada
