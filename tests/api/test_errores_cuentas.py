import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.usuarios.servicio import (
    CodigoInvalidoError,
    CredencialesInvalidasError,
    DemasiadosIntentosError,
    DesafioVencidoError,
    OperacionCuentaError,
    RegistroRechazadoError,
    SesionInvalidaError,
)
from bitcoinai.usuarios.validacion import DatoInvalidoError
from tests.apoyo.fuente_falsa import FuenteFalsa

ERRORES: dict[str, Exception] = {
    "dato": DatoInvalidoError("telefono", "Teléfono malo"),
    "repetido": RegistroRechazadoError("Ya existe"),
    "operacion": OperacionCuentaError("No se puede"),
    "credenciales": CredencialesInvalidasError(),
    "codigo": CodigoInvalidoError(),
    "desafio": DesafioVencidoError(),
    "sesion": SesionInvalidaError(),
    "intentos": DemasiadosIntentosError(61.2),
}


@pytest.fixture
def cliente() -> TestClient:
    app = crear_app(Configuracion(), FuenteFalsa())

    @app.get("/prueba/{nombre}")
    def lanzar(nombre: str) -> None:
        raise ERRORES[nombre]

    return TestClient(app)


@pytest.mark.parametrize(("nombre", "codigo"), [
    ("repetido", 409), ("operacion", 409), ("credenciales", 401), ("codigo", 401), ("desafio", 401), ("sesion", 401),
])
def test_codigo_http_de_cada_error(cliente: TestClient, nombre: str, codigo: int) -> None:
    r = cliente.get(f"/prueba/{nombre}")
    assert r.status_code == codigo
    assert set(r.json()) == {"error"}


def test_dato_invalido_dice_el_campo(cliente: TestClient) -> None:
    r = cliente.get("/prueba/dato")
    assert (r.status_code, r.json()) == (400, {"error": "Teléfono malo", "campo": "telefono"})


def test_demasiados_intentos_con_retry_after(cliente: TestClient) -> None:
    r = cliente.get("/prueba/intentos")
    assert r.status_code == 429
    assert r.headers["retry-after"] == "62"
    assert r.json()["error"] == "Demasiados intentos. Vuelve a intentarlo en 1 minuto."
