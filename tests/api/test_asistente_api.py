"""POST /api/asistente con una FuenteFalsa a precio 100."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.mercado import MercadoError
from bitcoinai.simulacion import ConsejoPiloto, GestorSimulaciones, LimitesPiloto
from tests.api.test_simulacion_api import post, registrado
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import crear_entorno


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa()


@pytest.fixture
def gestor(fuente: FuenteFalsa) -> Iterator[GestorSimulaciones]:
    g = GestorSimulaciones(fuente, "BTCUSDT")
    yield g
    g.detener_todos()


@pytest.fixture
def app(fuente: FuenteFalsa, gestor: GestorSimulaciones) -> FastAPI:
    return crear_app(Configuracion(), fuente, cuentas=crear_entorno().servicio, gestor=gestor)


def test_exige_sesion_antes_que_el_cuerpo(app: FastAPI) -> None:
    assert post(TestClient(app), "/api/asistente", '{"mensaje":5}').status_code == 401


def test_responde_con_los_datos_de_la_persona(app: FastAPI) -> None:
    c = registrado(app)
    post(c, "/api/ordenes", '{"tipo":"COMPRA","monto":500}')
    r = post(c, "/api/asistente", '{"mensaje":"¿tengo órdenes pendientes?"}')
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert list(cuerpo) == ["intencion", "respuesta", "accion", "sugerencias", "fuente"]
    assert cuerpo["fuente"] == "reglas"  # sin ANTHROPIC_API_KEY, solo reglas
    assert cuerpo["intencion"] == "ordenes" and "1 orden espera" in cuerpo["respuesta"]
    assert cuerpo["accion"] == {"tipo": "IR", "etiqueta": "Ir a Órdenes", "ruta": "/ordenes",
                                "orden": None, "alerta": None, "modo": None}
    assert len(cuerpo["sugerencias"]) >= 2


def test_pedir_encenderlo_no_lo_enciende(app: FastAPI) -> None:
    c = registrado(app)
    r = post(c, "/api/asistente", '{"mensaje":"enciende el bot"}').json()
    assert r["accion"]["tipo"] == "INICIAR_BOT"
    assert c.get("/api/bot/estado").json()["activo"] is False


def test_sin_precio_igual_responde(app: FastAPI, fuente: FuenteFalsa) -> None:
    c = registrado(app)
    fuente.error = MercadoError("Binance no responde")
    r = post(c, "/api/asistente", '{"mensaje":"¿cuánto he ganado?"}')
    assert r.status_code == 200 and "no pude leer el precio" in r.json()["respuesta"]


@pytest.mark.parametrize(("cuerpo", "fragmento"), [
    ('{"mensaje":"   "}', "Escribe un mensaje"),
    ('{}', "Escribe un mensaje"),
    ('{"mensaje":"' + "a" * 301 + '"}', "demasiado largo"),
    ('{"mensaje":5}', ""),
])
def test_mensajes_invalidos(app: FastAPI, cuerpo: str, fragmento: str) -> None:
    r = post(registrado(app), "/api/asistente", cuerpo)
    assert r.status_code == 400 and fragmento in r.json()["error"]


# ---------- con Claude (cliente falso: nunca se llama a la API real) ----------


class ClienteClaudeFalso:
    def __init__(self, falla: bool = False, herramienta: tuple[str, dict[str, object]] | None = None,
                 texto: str = "Con 10.000 USDT de práctica…") -> None:
        self.falla, self.herramienta, self.texto = falla, herramienta, texto
        self.pedidos: list[dict[str, object]] = []

    def crear(self, **parametros: object) -> object:
        from types import SimpleNamespace

        self.pedidos.append(parametros)
        if self.falla:
            raise RuntimeError("sin red")
        bloques = [SimpleNamespace(type="text", text=self.texto)] if self.texto else []
        if self.herramienta is not None:
            bloques.append(SimpleNamespace(type="tool_use", id="t1", name=self.herramienta[0],
                                           input=self.herramienta[1]))
        return SimpleNamespace(stop_reason="tool_use" if self.herramienta else "end_turn", content=bloques)


def app_con_claude(fuente: FuenteFalsa, gestor: GestorSimulaciones, cliente: ClienteClaudeFalso) -> FastAPI:
    from bitcoinai.asistente.conversador import Conversador

    return crear_app(Configuracion(), fuente, cuentas=crear_entorno().servicio, gestor=gestor,
                     conversador=Conversador(cliente))


def test_con_claude_el_texto_es_de_la_ia_y_la_accion_de_las_reglas(fuente: FuenteFalsa,
                                                                  gestor: GestorSimulaciones) -> None:
    cliente = ClienteClaudeFalso()
    c = registrado(app_con_claude(fuente, gestor, cliente))
    r = c.post("/api/asistente", json={"mensaje": "enciéndete", "historial": [
        {"rol": "usuario", "texto": "hola"}, {"rol": "bot", "texto": "¡Hola! ¿En qué te ayudo?"}]})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["fuente"] == "ia" and cuerpo["respuesta"] == "Con 10.000 USDT de práctica…"
    assert cuerpo["accion"]["tipo"] == "INICIAR_BOT"  # el botón lo decide el asistente de reglas
    mensajes = cliente.pedidos[0]["messages"]
    assert isinstance(mensajes, list) and len(mensajes) == 3
    ultimo = str(mensajes[-1]["content"])
    assert "Cartera: vale 10.000,00 USDT" in ultimo
    # A Claude nunca le llegan datos personales.
    for dato in ("ana@correo.co", "1023456789", "Ana", "3001234567"):
        assert dato not in ultimo


def test_si_claude_falla_responden_las_reglas(fuente: FuenteFalsa, gestor: GestorSimulaciones) -> None:
    c = registrado(app_con_claude(fuente, gestor, ClienteClaudeFalso(falla=True)))
    cuerpo = c.post("/api/asistente", json={"mensaje": "¿cuánto he ganado?"}).json()
    assert cuerpo["fuente"] == "reglas" and cuerpo["intencion"] == "ganancia"


def test_el_historial_se_valida(fuente: FuenteFalsa, gestor: GestorSimulaciones) -> None:
    c = registrado(app_con_claude(fuente, gestor, ClienteClaudeFalso()))
    largo = c.post("/api/asistente", json={"mensaje": "hola", "historial": [{"rol": "usuario", "texto": "x" * 2000}]})
    assert largo.status_code == 400


class PilotoQueFalla:
    """El piloto no puede decidir (por ejemplo, sin velas): el chat sigue con las reglas."""

    def aconsejar(self, intervalo: str, limites: LimitesPiloto) -> ConsejoPiloto:
        raise MercadoError("sin velas suficientes")


class PilotoFijo:
    """Devuelve siempre el mismo consejo, para verlo en el contexto de Claude."""

    def aconsejar(self, intervalo: str, limites: LimitesPiloto) -> ConsejoPiloto:
        return ConsejoPiloto(senal="MANTENER", probabilidad=0.5, confianza=0.0, exactitud=0.52, base=0.51,
                             riesgo=0.2, stop_loss=0.05, take_profit=0.1, volatilidad=0.01,
                             intervalo=intervalo, tiempo_vela=1, precio=100.0, motivo="sin ventaja clara")


def test_si_el_piloto_falla_claude_responde_sin_el_consejo(fuente: FuenteFalsa) -> None:
    cliente = ClienteClaudeFalso()
    gestor = GestorSimulaciones(fuente, "BTCUSDT", piloto=PilotoQueFalla())
    c = registrado(app_con_claude(fuente, gestor, cliente))

    r = c.post("/api/asistente", json={"mensaje": "¿qué hago?"})

    assert r.status_code == 200 and r.json()["fuente"] == "ia"
    mensajes = cliente.pedidos[0]["messages"]
    assert isinstance(mensajes, list)
    ultimo = str(mensajes[-1]["content"])
    assert "Cartera: vale" in ultimo  # los datos de práctica siguen ahí
    assert "Consejo actual de la IA" not in ultimo  # pero sin inventar un consejo


def test_el_consejo_del_piloto_viaja_en_el_contexto(fuente: FuenteFalsa) -> None:
    cliente = ClienteClaudeFalso()
    gestor = GestorSimulaciones(fuente, "BTCUSDT", piloto=PilotoFijo())
    c = registrado(app_con_claude(fuente, gestor, cliente))

    assert c.post("/api/asistente", json={"mensaje": "¿qué hago?"}).status_code == 200

    mensajes = cliente.pedidos[0]["messages"]
    assert isinstance(mensajes, list)
    ultimo = str(mensajes[-1]["content"])
    assert "Consejo actual de la IA (velas de 1h): MANTENER" in ultimo


def test_una_propuesta_valida_de_claude_reemplaza_la_accion(fuente: FuenteFalsa, gestor: GestorSimulaciones) -> None:
    cliente = ClienteClaudeFalso(herramienta=("proponer_orden", {"tipo": "COMPRA", "monto_usdt": 2000.129,
                                                                  "vender_todo": False}),
                                 texto="La IA ve más subida que la base; ¿pruebas con 2.000 USDT?")
    c = registrado(app_con_claude(fuente, gestor, cliente))
    cuerpo = c.post("/api/asistente", json={"mensaje": "¿qué me recomiendas?"}).json()
    assert cuerpo["fuente"] == "ia"
    assert cuerpo["accion"] == {"tipo": "ORDEN", "etiqueta": "Comprar 2.000,12 USDT de BTC", "ruta": None,
                                "orden": {"tipo": "COMPRA", "monto": 2000.12, "todo": False},
                                "alerta": None, "modo": None}
    assert cliente.pedidos[0]["tools"]  # Claude recibe las herramientas
    # Proponer no ejecuta nada: no hay órdenes.
    assert c.get("/api/ordenes").json()["cantidad"] == 0


def test_una_propuesta_que_no_alcanza_se_descarta(fuente: FuenteFalsa, gestor: GestorSimulaciones) -> None:
    cliente = ClienteClaudeFalso(herramienta=("proponer_orden", {"tipo": "COMPRA", "monto_usdt": 50_000,
                                                                  "vender_todo": False}))
    c = registrado(app_con_claude(fuente, gestor, cliente))
    cuerpo = c.post("/api/asistente", json={"mensaje": "hola"}).json()
    assert cuerpo["fuente"] == "ia" and cuerpo["accion"] is None


def test_solo_la_herramienta_sin_texto_igual_responde(fuente: FuenteFalsa, gestor: GestorSimulaciones) -> None:
    cliente = ClienteClaudeFalso(herramienta=("proponer_pagina", {"pagina": "ia"}), texto="")
    c = registrado(app_con_claude(fuente, gestor, cliente))
    cuerpo = c.post("/api/asistente", json={"mensaje": "¿dónde veo la IA?"}).json()
    assert cuerpo["fuente"] == "ia" and "confírmalo" in cuerpo["respuesta"]
    assert cuerpo["accion"]["tipo"] == "IR" and cuerpo["accion"]["ruta"] == "/ia"
