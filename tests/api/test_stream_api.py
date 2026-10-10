"""GET /api/stream contra un servidor uvicorn real (TestClient no sirve para conexiones que no terminan)."""

import json
import socket
import threading
import time
from collections.abc import Callable, Iterator

import httpx
import pytest
import uvicorn

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.api.publicador import Publicador, PublicadorDeUsuario
from bitcoinai.simulacion import GestorSimulaciones
from tests.api.test_cuentas_api import REGISTRO
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import crear_entorno


class Servidor:
    def __init__(self, url: str, publicador: Publicador) -> None:
        self.url = url
        self.publicador = publicador


@pytest.fixture
def servidor() -> Iterator[Servidor]:
    fuente = FuenteFalsa()
    publicador = Publicador(fuente, "BTCUSDT", maximo=2, periodo_precio=3600, periodo_latido=0.2)
    gestor = GestorSimulaciones(fuente, "BTCUSDT", crear_publicador=lambda u: PublicadorDeUsuario(publicador, u))
    app = crear_app(Configuracion(), fuente, publicador=publicador, cuentas=crear_entorno().servicio, gestor=gestor)

    enchufe = socket.socket()
    enchufe.bind(("127.0.0.1", 0))  # puerto libre elegido por el sistema
    puerto = enchufe.getsockname()[1]
    uvi = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False, timeout_graceful_shutdown=1))
    hilo = threading.Thread(target=uvi.run, kwargs={"sockets": [enchufe]}, daemon=True)
    hilo.start()
    esperar(lambda: uvi.started, "el servidor no arrancó")
    yield Servidor(f"http://127.0.0.1:{puerto}", publicador)
    uvi.should_exit = True
    hilo.join(10)
    enchufe.close()


def esperar(condicion: Callable[[], bool], mensaje: str, segundos: float = 5) -> None:
    limite = time.monotonic() + segundos
    while not condicion():
        if time.monotonic() > limite:
            raise AssertionError(mensaje)
        time.sleep(0.01)


def registrar(cliente: httpx.Client, correo: str = "ana@correo.co", documento: str = "1023456789") -> None:
    r = cliente.post("/api/cuentas/registro", json={**REGISTRO, "correo": correo, "numeroDocumento": documento})
    assert r.status_code == 201, r.text


def test_envia_saludo_eventos_y_latidos(servidor: Servidor) -> None:
    with httpx.Client(base_url=servidor.url, timeout=5) as cliente:
        registrar(cliente)
        with cliente.stream("GET", "/api/stream") as r:
            revisar_stream(r, cliente)


def revisar_stream(r: httpx.Response, cliente: httpx.Client) -> None:
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"
    assert r.headers["access-control-allow-origin"] == "*"
    lineas = r.iter_lines()
    assert next(lineas) == "retry: 5000"
    assert next(lineas) == ": conectado"
    assert next(lineas) == ""
    assert next(lineas) == ": latido"  # cada 0,2 s en la prueba
    assert next(lineas) == ""

    creada = cliente.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 500})
    assert creada.status_code == 201
    while next(lineas) != "event: orden":
        pass
    datos = next(lineas)
    assert datos.startswith("data: ")
    orden = json.loads(datos.removeprefix("data: "))
    assert (orden["id"], orden["estado"], orden["motivo"]) == (1, "PENDIENTE", "manual")


def test_al_desconectarse_se_quita_el_suscriptor(servidor: Servidor) -> None:
    with httpx.Client(base_url=servidor.url, timeout=5) as cliente:
        with cliente.stream("GET", "/api/stream") as r:
            lineas = r.iter_lines()
            next(lineas)
            assert servidor.publicador.cantidad_suscriptores() == 1
    esperar(lambda: servidor.publicador.cantidad_suscriptores() == 0, "el suscriptor no se quitó")


def test_superar_el_maximo_da_503(servidor: Servidor) -> None:
    with httpx.Client(base_url=servidor.url, timeout=5) as cliente:
        with cliente.stream("GET", "/api/stream") as uno, cliente.stream("GET", "/api/stream") as dos:
            # Hay que conservar los iteradores: si se descartan, httpx cierra la conexión.
            lineas_uno, lineas_dos = uno.iter_lines(), dos.iter_lines()
            next(lineas_uno)
            next(lineas_dos)
            assert servidor.publicador.cantidad_suscriptores() == 2
            tercero = cliente.get("/api/stream")
            assert tercero.status_code == 503
            assert tercero.json() == {"error": "Demasiadas conexiones de tiempo real abiertas (máximo 2); "
                                               "intenta más tarde"}
    esperar(lambda: servidor.publicador.cantidad_suscriptores() == 0, "los suscriptores no se quitaron")


def test_otro_metodo_da_405(servidor: Servidor) -> None:
    r = httpx.post(f"{servidor.url}/api/stream")
    assert r.status_code == 405
    assert r.headers["allow"] == "GET"
    assert "no permitido" in r.json()["error"]


def test_sin_publicador_no_hay_stream() -> None:
    from fastapi.testclient import TestClient

    r = TestClient(crear_app(Configuracion(), FuenteFalsa())).get("/api/stream")
    assert r.status_code == 404


def test_las_ordenes_de_un_usuario_no_le_llegan_a_otro(servidor: Servidor) -> None:
    with httpx.Client(base_url=servidor.url, timeout=5) as ana, httpx.Client(base_url=servidor.url, timeout=5) as luis:
        registrar(ana)
        registrar(luis, "luis@correo.co", "79123456")
        with luis.stream("GET", "/api/stream") as r:
            lineas = r.iter_lines()
            assert next(lineas) == "retry: 5000"
            assert ana.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 500}).status_code == 201
            assert luis.post("/api/ordenes", json={"tipo": "COMPRA", "monto": 7}).status_code == 201
            while (linea := next(lineas)) != "event: orden":
                assert linea in ("", ": conectado", ": latido")
            orden = json.loads(next(lineas).removeprefix("data: "))
            assert orden["monto"] == 7  # la primera que le llega es la suya, no la de Ana
