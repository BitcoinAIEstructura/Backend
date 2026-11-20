"""El botón «Entrar a la demo»: abre la cuenta de DEMO_CORREO sin contraseña, y esa cuenta
no puede cambiar su seguridad."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from tests.api.test_simulacion_api import registrado
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import crear_entorno

DEMO = "demo@nexabit.test"


def app_con(demo_correo: str = "") -> FastAPI:
    return crear_app(Configuracion(demo_correo=demo_correo), FuenteFalsa(), cuentas=crear_entorno().servicio)


def test_sin_demo_configurada_no_hay_boton_ni_entrada() -> None:
    c = TestClient(app_con())
    assert c.get("/api/cuentas/demo").json() == {"disponible": False}
    r = c.post("/api/cuentas/demo")
    assert r.status_code == 404 and "no está disponible" in r.json()["error"]


def test_demo_configurada_pero_sin_cuenta_responde_404() -> None:
    c = TestClient(app_con(DEMO))
    assert c.get("/api/cuentas/demo").json() == {"disponible": True}
    assert c.post("/api/cuentas/demo").status_code == 404


def test_entra_a_la_cuenta_demo_sin_contrasena_y_el_navegador_no_elige_la_cuenta() -> None:
    app = app_con(DEMO)
    registrado(app, correo=DEMO)
    registrado(app, correo="otra@correo.co", documento="1098765432")
    visitante = TestClient(app)
    r = visitante.post("/api/cuentas/demo", json={"correo": "otra@correo.co"})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["correo"] == DEMO  # el cuerpo se ignora: siempre la demo
    assert visitante.get("/api/cuentas/yo").json()["usuario"]["correo"] == DEMO
    actividad = visitante.get("/api/cuentas/actividad").json()["eventos"]
    assert any("(demo)" in (e["detalle"] or "") for e in actividad)


def test_la_cuenta_demo_no_puede_cambiar_su_seguridad() -> None:
    app = app_con(DEMO)
    registrado(app, correo=DEMO)
    visitante = TestClient(app)
    assert visitante.post("/api/cuentas/demo").status_code == 200
    bloqueadas = [
        ("/api/cuentas/contrasena", {"contrasenaActual": "x", "contrasenaNueva": "OtraClave#2026x"}),
        ("/api/cuentas/dos-pasos", None),
        ("/api/cuentas/dos-pasos/confirmar", {"codigo": "123456"}),
        ("/api/cuentas/dos-pasos/desactivar", {"contrasena": "x", "codigo": "123456"}),
        ("/api/cuentas/dos-pasos/codigos", {"codigo": "123456"}),
        ("/api/cuentas/sesiones/cerrar-otras", None),
    ]
    for ruta, cuerpo in bloqueadas:
        r = visitante.post(ruta, json=cuerpo) if cuerpo is not None else visitante.post(ruta)
        assert r.status_code == 403, (ruta, r.text)
        assert "demostración" in r.json()["error"]
    assert visitante.delete("/api/cuentas/sesiones/1").status_code == 403
    # Lo demás sí funciona: ver su cartera, sus sesiones, su actividad.
    assert visitante.get("/api/cuentas/sesiones").status_code == 200


def test_las_demas_cuentas_si_cambian_su_seguridad() -> None:
    app = app_con(DEMO)
    registrado(app, correo=DEMO)
    otra = registrado(app, correo="otra@correo.co", documento="1098765432")
    assert otra.post("/api/cuentas/dos-pasos").status_code == 200
