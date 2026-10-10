"""Registro, inicio y cierre de sesión por HTTP, con la cookie de sesión."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.seguridad import totp
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import CLIENTE, CONTRASENA, Entorno, crear_entorno

REGISTRO: dict[str, Any] = {
    "nombre": "Ana", "apellido": "Pérez", "correo": "Ana@Correo.co", "tipoDocumento": "CC",
    "numeroDocumento": "1.023.456.789", "telefono": "300 123 4567", "contrasena": CONTRASENA,
}


@pytest.fixture
def entorno() -> Entorno:
    return crear_entorno()


@pytest.fixture
def cliente(entorno: Entorno) -> TestClient:
    return TestClient(crear_app(Configuracion(), FuenteFalsa(), cuentas=entorno.servicio))


def test_registro_abre_sesion_con_cookie_segura(cliente: TestClient) -> None:
    r = cliente.post("/api/cuentas/registro", json=REGISTRO)
    assert r.status_code == 201, r.text
    usuario = r.json()["usuario"]
    assert usuario == {"id": 1, "nombre": "Ana", "apellido": "Pérez", "correo": "ana@correo.co",
                       "tipoDocumento": "CC", "documento": "******6789", "telefono": "+57******4567",
                       "verificacionDosPasos": False, "creadoEn": usuario["creadoEn"]}
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("sesion=")
    for atributo in ("HttpOnly", "SameSite=strict", "Path=/", "Max-Age=43200"):
        assert atributo in cookie
    assert r.headers["cache-control"] == "no-store"
    assert cliente.get("/api/cuentas/yo").json()["usuario"]["correo"] == "ana@correo.co"


def test_registro_con_datos_invalidos_dice_el_campo(cliente: TestClient) -> None:
    r = cliente.post("/api/cuentas/registro", json={**REGISTRO, "telefono": "123"})
    assert r.status_code == 400
    assert r.json()["campo"] == "telefono"
    r = cliente.post("/api/cuentas/registro", json={**REGISTRO, "contrasena": "corta"})
    assert r.json()["campo"] == "contrasena"
    falta = {k: v for k, v in REGISTRO.items() if k != "telefono"}
    assert cliente.post("/api/cuentas/registro", json=falta).json()["error"] == "Falta el campo 'telefono'"
    extra = cliente.post("/api/cuentas/registro", json={**REGISTRO, "esAdmin": True})
    assert extra.json()["error"] == "Campo no permitido: 'esAdmin'"
    largo = cliente.post("/api/cuentas/registro", json={**REGISTRO, "nombre": "A" * 500})
    assert largo.json()["error"] == "El campo 'nombre' es demasiado largo"


def test_registro_repetido_da_409(cliente: TestClient) -> None:
    cliente.post("/api/cuentas/registro", json=REGISTRO)
    r = cliente.post("/api/cuentas/registro", json={**REGISTRO, "correo": "otra@correo.co"})
    assert r.status_code == 409


def test_sin_sesion_da_401(cliente: TestClient) -> None:
    r = cliente.get("/api/cuentas/yo")
    assert (r.status_code, r.json()["error"]) == (401, "Tu sesión terminó; vuelve a iniciar sesión")
    cliente.cookies.set("sesion", "inventada")
    assert cliente.get("/api/cuentas/yo").status_code == 401


def test_iniciar_y_cerrar_sesion(cliente: TestClient) -> None:
    cliente.post("/api/cuentas/registro", json=REGISTRO)
    cliente.cookies.clear()
    malo = cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": "mala"})
    assert (malo.status_code, malo.json()["error"]) == (401, "Correo o contraseña incorrectos")
    r = cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": CONTRASENA})
    assert r.status_code == 200 and r.json()["segundoPaso"] is False
    assert r.json()["usuario"]["id"] == 1
    assert cliente.get("/api/cuentas/yo").status_code == 200
    salida = cliente.delete("/api/sesion")
    assert salida.status_code == 204 and 'sesion=""' in salida.headers["set-cookie"]
    assert cliente.get("/api/cuentas/yo").status_code == 401
    assert cliente.delete("/api/sesion").status_code == 204  # cerrar dos veces no falla


def test_bloqueo_por_intentos_da_429(cliente: TestClient) -> None:
    for _ in range(5):
        cliente.post("/api/sesion", json={"correo": "x@correo.co", "contrasena": "mala"})
    r = cliente.post("/api/sesion", json={"correo": "x@correo.co", "contrasena": "mala"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_inicio_con_verificacion_en_dos_pasos(cliente: TestClient, entorno: Entorno) -> None:
    cliente.post("/api/cuentas/registro", json=REGISTRO)
    config = entorno.servicio.iniciar_dos_pasos(1)
    codigo = totp.codigo_hotp(config.secreto, totp.paso(entorno.reloj.ahora))
    entorno.servicio.confirmar_dos_pasos(1, codigo, CLIENTE)
    entorno.reloj.ahora += 30
    cliente.cookies.clear()
    r = cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": CONTRASENA})
    assert r.json() == {"segundoPaso": True}
    assert "desafio=" in r.headers["set-cookie"] and "HttpOnly" in r.headers["set-cookie"]
    assert cliente.get("/api/cuentas/yo").status_code == 401  # todavía no hay sesión
    assert cliente.post("/api/sesion/codigo", json={"codigo": "000000"}).status_code == 401
    bueno = totp.codigo_hotp(config.secreto, totp.paso(entorno.reloj.ahora))
    r = cliente.post("/api/sesion/codigo", json={"codigo": bueno})
    assert r.status_code == 200 and r.json()["usuario"]["verificacionDosPasos"] is True
    assert cliente.get("/api/cuentas/yo").status_code == 200


def test_codigo_sin_desafio(cliente: TestClient) -> None:
    r = cliente.post("/api/sesion/codigo", json={"codigo": "123456"})
    assert r.status_code == 401 and "vuelve a escribir tu contraseña" in r.json()["error"]


def test_cookie_segura_con_prefijo_host(entorno: Entorno) -> None:
    app = crear_app(Configuracion(cookie_segura=True), FuenteFalsa(), cuentas=entorno.servicio)
    r = TestClient(app, base_url="https://testserver").post("/api/cuentas/registro", json=REGISTRO)
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("__Host-sesion=") and "Secure" in cookie


def test_ip_real_solo_con_confiar_proxy() -> None:
    for confiar, esperada in ((False, "testclient"), (True, "203.0.113.7")):
        app = crear_app(Configuracion(confiar_proxy=confiar), FuenteFalsa(), cuentas=crear_entorno().servicio)
        c = TestClient(app)
        c.post("/api/cuentas/registro", json=REGISTRO, headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
        servicio = app.state.cuentas
        assert servicio.actividad_reciente(1).primero().ip == esperada

