"""Límite de peticiones por IP (MiddlewareLimite)."""

from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from tests.apoyo.fuente_falsa import FuenteFalsa


def cliente(**config: object) -> TestClient:
    return TestClient(crear_app(Configuracion(**config), FuenteFalsa()))  # type: ignore[arg-type]


def test_las_rutas_costosas_tienen_su_propio_limite() -> None:
    c = cliente(limite_costosas=2, limite_general=100)
    for _ in range(2):
        assert c.get("/api/si-hubiera", params={"fecha": "2024-01-01", "monto": "1"}).status_code == 200
    r = c.get("/api/si-hubiera", params={"fecha": "2024-01-01", "monto": "1"})
    assert r.status_code == 429
    assert "Demasiadas peticiones" in r.json()["error"]
    assert int(r.headers["Retry-After"]) >= 1
    assert c.get("/api/precio").status_code == 200  # las demás siguen


def test_limite_general_y_health_no_cuenta() -> None:
    c = cliente(limite_general=3)
    for _ in range(3):
        assert c.get("/api/precio").status_code == 200
    assert c.get("/api/velas").status_code == 429
    assert c.get("/health").status_code == 200


def test_solo_cree_x_forwarded_for_si_se_confia_en_el_proxy() -> None:
    sin_confiar = cliente(limite_general=1)
    sin_confiar.get("/api/precio", headers={"X-Forwarded-For": "1.1.1.1"})
    # Inventarse otra IP no sirve: para el servidor sigue siendo el mismo cliente.
    assert sin_confiar.get("/api/precio", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429

    confiando = cliente(limite_general=1, confiar_proxy=True)
    assert confiando.get("/api/precio", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert confiando.get("/api/precio", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert confiando.get("/api/precio", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429


def test_configuracion_desde_el_entorno() -> None:
    config = Configuracion.desde_entorno({"LIMITE_GENERAL": "50", "LIMITE_COSTOSAS": "5"})
    assert (config.limite_general, config.limite_costosas) == (50, 5)
