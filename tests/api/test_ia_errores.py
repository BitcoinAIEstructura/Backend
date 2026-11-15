"""Los caminos de error de la IA por HTTP.

- Sin datos suficientes para entrenar con honestidad, ``/api/ia/predicciones`` responde 503
  (es una condición esperada mientras el mercado no tiene velas), no un 500.
- Si el precio no está disponible, ``/api/ia/fuentes`` sigue respondiendo el panorama externo.
- Sin fuentes externas configuradas, ``/api/ia/fuentes`` devuelve listas vacías.
"""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.externos import DatosExternos
from bitcoinai.ia.servicio import DatosInsuficientesError, ServicioIA
from bitcoinai.mercado import MercadoError


class FuenteSinPrecio:
    """Fuente de mercado que responde lo justo: pedir el precio lanza MercadoError."""

    def obtener_precio_actual(self, simbolo: str) -> float:
        raise MercadoError("Binance no respondió")

    def obtener_velas(self, *args: object, **kwargs: object) -> Any:
        raise MercadoError("Binance no respondió")


class IASinDatos:
    """Servicio de IA que todavía no puede entrenar."""

    def predecir(self, intervalo: object) -> Any:
        raise DatosInsuficientesError("Faltan velas para entrenar: hay 40 y se necesitan 200")

    def consejo(self, *args: object, **kwargs: object) -> Any:
        raise DatosInsuficientesError("sin velas")


class ExternosFalsos:
    """Panorama externo fijo, para no salir a internet."""

    def panorama(self, intervalo: object, precio: float | None) -> Any:
        return SimpleNamespace(
            lecturas=[SimpleNamespace(id="miedo", nombre="Miedo y codicia", fuente="alternative.me", valor=55.0,
                                      valor_texto="55 (Neutral)", explicacion="El ánimo del mercado.")],
            errores={"dvol": "No respondió"},
            actualizado_en=1_700_000_000_000,
            precio=precio,
        )


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(crear_app(Configuracion(), FuenteSinPrecio(), ia=cast(ServicioIA, IASinDatos()),
                               externos=cast(DatosExternos, ExternosFalsos())))


def test_sin_velas_suficientes_responde_503(cliente: TestClient) -> None:
    r = cliente.get("/api/ia/predicciones", params={"intervalo": "1h"})
    assert r.status_code == 503
    assert "Faltan velas para entrenar" in r.json()["error"]


def test_fuentes_sin_precio_igual_responde_el_panorama(cliente: TestClient) -> None:
    r = cliente.get("/api/ia/fuentes", params={"intervalo": "1h"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert [lectura["id"] for lectura in cuerpo["lecturas"]] == ["miedo"]
    assert cuerpo["errores"] == [{"id": "dvol", "motivo": "No respondió"}]
    assert cuerpo["actualizadoEn"] == 1_700_000_000_000


def test_sin_fuentes_externas_devuelve_listas_vacias() -> None:
    app = crear_app(Configuracion(), FuenteSinPrecio(), ia=cast(ServicioIA, IASinDatos()))
    r = TestClient(app).get("/api/ia/fuentes")
    assert r.status_code == 200
    assert r.json() == {"lecturas": [], "errores": [], "actualizadoEn": None}


def test_un_intervalo_invalido_da_400(cliente: TestClient) -> None:
    r = cliente.get("/api/ia/predicciones", params={"intervalo": "7h"})
    assert r.status_code == 400
    assert "intervalo" in r.json()["error"]
