"""Centro de seguridad por HTTP: verificación en dos pasos, sesiones, actividad y contraseña."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.seguridad import totp
from tests.api.test_cuentas_api import REGISTRO
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import CONTRASENA, Entorno, crear_entorno


@pytest.fixture
def entorno() -> Entorno:
    return crear_entorno()


@pytest.fixture
def app_cuentas(entorno: Entorno) -> FastAPI:
    return crear_app(Configuracion(), FuenteFalsa(), cuentas=entorno.servicio)


@pytest.fixture
def cliente(app_cuentas: FastAPI) -> TestClient:
    c = TestClient(app_cuentas)
    assert c.post("/api/cuentas/registro", json=REGISTRO).status_code == 201
    return c


def codigo(entorno: Entorno, secreto: str) -> str:
    return totp.codigo_hotp(secreto, totp.paso(entorno.reloj.ahora))


def test_todo_pide_sesion(app_cuentas: FastAPI) -> None:
    anonimo = TestClient(app_cuentas)
    for metodo, ruta in (("POST", "/api/cuentas/dos-pasos"), ("GET", "/api/cuentas/sesiones"),
                         ("GET", "/api/cuentas/actividad"), ("POST", "/api/cuentas/sesiones/cerrar-otras"),
                         ("DELETE", "/api/cuentas/sesiones/1")):
        assert anonimo.request(metodo, ruta).status_code == 401, ruta


def test_activar_y_desactivar_dos_pasos(cliente: TestClient, entorno: Entorno) -> None:
    inicio = cliente.post("/api/cuentas/dos-pasos").json()
    assert inicio["uri"].startswith("otpauth://totp/") and len(inicio["secreto"]) == 32
    assert cliente.post("/api/cuentas/dos-pasos/confirmar", json={"codigo": "000000"}).status_code == 401
    r = cliente.post("/api/cuentas/dos-pasos/confirmar", json={"codigo": codigo(entorno, inicio["secreto"])})
    respaldo = r.json()["codigosRespaldo"]
    assert len(respaldo) == 10
    assert cliente.get("/api/cuentas/yo").json()["usuario"]["verificacionDosPasos"] is True
    assert cliente.post("/api/cuentas/dos-pasos").status_code == 409

    nuevos = cliente.post("/api/cuentas/dos-pasos/codigos", json={"codigo": respaldo[0]}).json()["codigosRespaldo"]
    assert set(nuevos).isdisjoint(respaldo)
    malo = cliente.post("/api/cuentas/dos-pasos/desactivar", json={"contrasena": "mala", "codigo": nuevos[0]})
    assert malo.status_code == 401
    r = cliente.post("/api/cuentas/dos-pasos/desactivar", json={"contrasena": CONTRASENA, "codigo": nuevos[0]})
    assert r.status_code == 204
    assert cliente.get("/api/cuentas/yo").json()["usuario"]["verificacionDosPasos"] is False


def test_sesiones_de_varios_dispositivos(cliente: TestClient, app_cuentas: FastAPI) -> None:
    otro = TestClient(app_cuentas)
    otro.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": CONTRASENA},
              headers={"User-Agent": "Telefono/1.0"})
    lista = cliente.get("/api/cuentas/sesiones").json()["sesiones"]
    assert len(lista) == 2
    assert [s["actual"] for s in lista].count(True) == 1
    assert set(lista[0]) == {"id", "actual", "ip", "agente", "creadaEn", "ultimaActividad", "expiraEn"}
    del_telefono = next(s for s in lista if s["agente"] == "Telefono/1.0")
    assert cliente.delete(f"/api/cuentas/sesiones/{del_telefono['id']}").status_code == 204
    assert otro.get("/api/cuentas/yo").status_code == 401
    assert cliente.delete(f"/api/cuentas/sesiones/{del_telefono['id']}").status_code == 409
    assert cliente.post("/api/cuentas/sesiones/cerrar-otras").json() == {"cerradas": 0}


def test_actividad(cliente: TestClient) -> None:
    eventos = cliente.get("/api/cuentas/actividad?limite=1").json()["eventos"]
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "INICIO_SESION" and eventos[0]["descripcion"] == "Inicio de sesión"
    assert len(cliente.get("/api/cuentas/actividad").json()["eventos"]) == 2


def test_cambiar_contrasena(cliente: TestClient) -> None:
    cuerpo = {"contrasenaActual": CONTRASENA, "contrasenaNueva": "corta"}
    r = cliente.post("/api/cuentas/contrasena", json=cuerpo)
    assert (r.status_code, r.json()["campo"]) == (400, "contrasenaNueva")
    cuerpo["contrasenaNueva"] = "Sol-Azul-Brillante-9"
    assert cliente.post("/api/cuentas/contrasena", json=cuerpo).status_code == 204
    cliente.cookies.clear()
    viejo = cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": CONTRASENA})
    assert viejo.status_code == 401
    nuevo = cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": "Sol-Azul-Brillante-9"})
    assert nuevo.status_code == 200
