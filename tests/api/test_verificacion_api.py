"""Confirmar el correo por HTTP: registro → código por correo → sesión, con la cookie de la verificación."""

import re

import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.notificaciones import BuzonMemoria
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.seguridad.contrasenas import PARAMETROS_RAPIDOS_PARA_PRUEBAS, HashContrasenas
from bitcoinai.usuarios.servicio import ServicioCuentas
from tests.api.test_cuentas_api import REGISTRO
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import CONTRASENA, Reloj


class Entorno:
    def __init__(self) -> None:
        bd = BaseDatos(":memory:")
        migrar(bd)
        self.reloj = Reloj()
        self.buzon = BuzonMemoria()
        servicio = ServicioCuentas(bd, Cifrador(bytes(32)), HashContrasenas(PARAMETROS_RAPIDOS_PARA_PRUEBAS),
                                   reloj_ms=self.reloj.ms, reloj_s=self.reloj, correo=self.buzon)
        self.cliente = TestClient(crear_app(Configuracion(), FuenteFalsa(), cuentas=servicio))

    def codigo(self) -> str:
        encontrado = re.search(r"\d{6}", self.buzon.ultimo().asunto)
        assert encontrado is not None
        return encontrado.group(0)


@pytest.fixture
def e() -> Entorno:
    return Entorno()


def test_registro_pide_el_codigo_sin_abrir_sesion(e: Entorno) -> None:
    r = e.cliente.post("/api/cuentas/registro", json=REGISTRO)
    assert r.status_code == 201, r.text
    assert r.json() == {"verificarCorreo": True, "correo": "a***@correo.co"}
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("verificacion=") and "HttpOnly" in cookie and "Max-Age=86400" in cookie
    assert "sesion=" not in cookie
    assert e.cliente.get("/api/cuentas/yo").status_code == 401


def test_el_codigo_abre_la_sesion_y_borra_la_cookie(e: Entorno) -> None:
    e.cliente.post("/api/cuentas/registro", json=REGISTRO)
    malo = e.cliente.post("/api/cuentas/verificar-correo", json={"codigo": "999999" if e.codigo() != "999999"
                                                                 else "111111"})
    assert malo.status_code == 401 and "no es válido" in malo.json()["error"]
    r = e.cliente.post("/api/cuentas/verificar-correo", json={"codigo": e.codigo()})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["correo"] == "ana@correo.co"
    assert any(c.startswith("sesion=") for c in r.headers.get_list("set-cookie"))
    assert any(c.startswith('verificacion=""') for c in r.headers.get_list("set-cookie"))
    assert e.cliente.get("/api/cuentas/yo").status_code == 200


def test_iniciar_sesion_sin_confirmar_pide_el_codigo(e: Entorno) -> None:
    e.cliente.post("/api/cuentas/registro", json=REGISTRO)
    e.cliente.cookies.clear()
    r = e.cliente.post("/api/sesion", json={"correo": "ana@correo.co", "contrasena": CONTRASENA})
    assert r.status_code == 200
    assert r.json() == {"segundoPaso": False, "verificarCorreo": True, "correo": "a***@correo.co"}
    assert e.cliente.post("/api/cuentas/verificar-correo", json={"codigo": e.codigo()}).status_code == 200


def test_reenviar_codigo(e: Entorno) -> None:
    assert e.cliente.post("/api/cuentas/reenviar-codigo").status_code == 410  # sin cookie
    e.cliente.post("/api/cuentas/registro", json=REGISTRO)
    pronto = e.cliente.post("/api/cuentas/reenviar-codigo")
    assert pronto.status_code == 429 and pronto.headers["retry-after"] == "60"
    e.reloj.ahora += 61
    r = e.cliente.post("/api/cuentas/reenviar-codigo")
    assert r.status_code == 200 and r.json() == {"correo": "a***@correo.co"}
    assert e.buzon.enviados.tamanio() == 2


def test_cuerpo_invalido_y_cookie_inventada(e: Entorno) -> None:
    assert e.cliente.post("/api/cuentas/verificar-correo", json={"codigo": 123456}).status_code == 400
    e.cliente.cookies.set("verificacion", "inventada")
    r = e.cliente.post("/api/cuentas/verificar-correo", json={"codigo": "123456"})
    assert r.status_code == 410 and "pide uno nuevo" in r.json()["error"]
