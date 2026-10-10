from fastapi.testclient import TestClient

from bitcoinai.__main__ import construir
from bitcoinai.api import Configuracion


def test_construir_arma_la_app_con_health_disponible_sin_consultar_binance() -> None:
    app = construir(Configuracion())
    respuesta = TestClient(app).get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
