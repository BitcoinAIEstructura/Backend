import os
import re
from email import message_from_bytes, policy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bitcoinai.__main__ import cargar_env, construir
from bitcoinai.api import Configuracion
from bitcoinai.api.publicador import Publicador
from bitcoinai.seguridad.claves import ARCHIVO_CLAVE
from bitcoinai.seguridad.contrasenas import PARAMETROS_RAPIDOS_PARA_PRUEBAS, HashContrasenas
from tests.api.test_cuentas_api import REGISTRO


@pytest.fixture(autouse=True)
def sin_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Que ninguna prueba mande correos de verdad aunque el equipo tenga SMTP configurado."""
    for nombre in ("SMTP_USUARIO", "SMTP_CONTRASENA", "SMTP_HOST", "SMTP_PUERTO", "CORREO_REMITENTE"):
        monkeypatch.delenv(nombre, raising=False)


def registrar_y_confirmar(cliente: TestClient, carpeta: Path) -> None:
    """Crea la cuenta y la confirma con el código del correo, que sin SMTP queda en <DATA_DIR>/correos."""
    r = cliente.post("/api/cuentas/registro", json=REGISTRO)
    assert r.status_code == 201 and r.json() == {"verificarCorreo": True, "correo": "a***@correo.co"}
    [archivo] = (carpeta / "correos").glob("*.eml")
    correo = message_from_bytes(archivo.read_bytes(), policy=policy.default)
    assert correo["To"] == "ana@correo.co"
    codigo = re.search(r"(\d{6}) es tu código", str(correo["Subject"]))
    assert codigo is not None
    assert cliente.post("/api/cuentas/verificar-correo", json={"codigo": codigo.group(1)}).status_code == 200


def test_construir_arma_la_app_con_health_disponible_sin_consultar_binance(tmp_path: Path) -> None:
    app = construir(Configuracion(data_dir=str(tmp_path)))
    respuesta = TestClient(app).get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
    assert isinstance(app.state.publicador, Publicador)


def test_la_simulacion_de_cada_usuario_sobrevive_a_un_reinicio(tmp_path: Path) -> None:
    config = Configuracion(data_dir=str(tmp_path))
    hasher = HashContrasenas(PARAMETROS_RAPIDOS_PARA_PRUEBAS)
    with TestClient(construir(config, hasher)) as cliente:
        registrar_y_confirmar(cliente, tmp_path)
        assert cliente.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 100}).status_code == 201
        assert cliente.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 200}).status_code == 201
        assert cliente.delete("/api/ordenes/1").status_code == 200
    assert not (tmp_path / "ordenes.json").exists()  # ahora va a la base de datos, no a archivos JSON

    with TestClient(construir(config, hasher)) as cliente:  # "reinicio": app nueva, misma base
        r = cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": REGISTRO["contrasena"]})
        assert r.status_code == 200
        ordenes = cliente.get("/api/ordenes").json()["ordenes"]
        assert [(o["id"], o["estado"]) for o in ordenes] == [(2, "PENDIENTE"), (1, "CANCELADA")]
        assert cliente.get("/api/historial?limite=1").json()["eventos"][0]["tipo"] == "ORDEN_CANCELADA"
        assert cliente.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 5}).json()["id"] == 3


def test_las_cuentas_sobreviven_a_un_reinicio(tmp_path: Path) -> None:
    config = Configuracion(data_dir=str(tmp_path))
    hasher = HashContrasenas(PARAMETROS_RAPIDOS_PARA_PRUEBAS)
    with TestClient(construir(config, hasher)) as cliente:
        registrar_y_confirmar(cliente, tmp_path)
    assert (tmp_path / "bitcoinai.db").exists() and (tmp_path / ARCHIVO_CLAVE).exists()
    with TestClient(construir(config, hasher)) as cliente:  # misma base y misma clave
        r = cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": REGISTRO["contrasena"]})
        assert r.status_code == 200
        assert r.json()["usuario"]["documento"] == "******6789"  # se descifra con la clave guardada


def test_cargar_env_lee_el_archivo_sin_pisar_el_entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archivo = tmp_path / ".env"
    archivo.write_text('# comentario\nSMTP_USUARIO=grupo@gmail.com\nSMTP_CONTRASENA="abcd efgh"\nPORT=9\n\nsin igual\n',
                       encoding="utf-8")
    monkeypatch.setenv("PORT", "8081")
    try:
        assert cargar_env(str(archivo)) == 2
        assert os.environ["SMTP_USUARIO"] == "grupo@gmail.com" and os.environ["SMTP_CONTRASENA"] == "abcd efgh"
        assert os.environ["PORT"] == "8081"  # lo que ya estaba en el entorno gana
        assert cargar_env(str(tmp_path / "no-existe")) == 0
    finally:  # que no les llegue a las demás pruebas
        os.environ.pop("SMTP_USUARIO", None)
        os.environ.pop("SMTP_CONTRASENA", None)
