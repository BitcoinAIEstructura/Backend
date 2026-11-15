"""El armado de la petición a Claude y el adaptador del SDK oficial.

La API exige que los turnos alternen: dos mensajes seguidos de la misma persona se funden
en uno, y los datos de práctica viajan pegados al último mensaje del usuario. También se
prueba que sin el paquete ``anthropic`` el chat siga funcionando con las reglas.
"""

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from bitcoinai.asistente import conversador as modulo_conversador
from bitcoinai.asistente.conversador import Conversador, Turno, _ClienteAnthropic, conversador_desde_entorno


class ClienteFalso:
    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []

    def crear(self, **parametros: Any) -> Any:
        self.pedidos.append(parametros)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="hola")])


def conversador() -> Conversador:
    return Conversador(ClienteFalso(), "claude-prueba")


def test_dos_mensajes_seguidos_de_la_persona_se_funden_en_uno() -> None:
    peticion = conversador().parametros(
        "¿y el bot?", (Turno("usuario", "hola"), Turno("usuario", "¿cómo va?")), "Cartera: 10 USDT")
    mensajes = peticion["messages"]
    assert len(mensajes) == 1
    assert mensajes[0]["role"] == "user"
    assert mensajes[0]["content"].startswith("hola\n\n¿cómo va?")
    assert mensajes[0]["content"].endswith("<datos_de_practica>\nCartera: 10 USDT\n</datos_de_practica>\n\n¿y el bot?")


def test_dos_respuestas_seguidas_del_bot_tambien_se_funden() -> None:
    peticion = conversador().parametros(
        "sigo", (Turno("usuario", "hola"), Turno("bot", "buenas"), Turno("bot", "¿en qué ayudo?")), "x")
    mensajes = peticion["messages"]
    assert [m["role"] for m in mensajes] == ["user", "assistant", "user"]
    assert mensajes[1]["content"] == "buenas\n\n¿en qué ayudo?"


def test_la_conversacion_no_puede_empezar_con_el_bot() -> None:
    peticion = conversador().parametros("hola", (Turno("bot", "buenas"), Turno("usuario", "hey")), "x")
    [mensaje] = peticion["messages"]
    assert mensaje["role"] == "user"
    assert "buenas" not in mensaje["content"]  # el saludo del bot se descarta
    assert mensaje["content"].startswith("hey\n\n<datos_de_practica>")


def test_el_adaptador_llama_al_sdk_oficial(monkeypatch: pytest.MonkeyPatch) -> None:
    creados: list[Any] = []

    class AnthropicFalso:
        def __init__(self, timeout: float, max_retries: int) -> None:
            self.timeout, self.max_retries = timeout, max_retries
            self.llamadas: list[dict[str, Any]] = []
            self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear))
            creados.append(self)

        def _crear(self, **parametros: Any) -> str:
            self.llamadas.append(parametros)
            return "respuesta-de-claude"

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=AnthropicFalso))

    adaptador = _ClienteAnthropic(espera_s=12)
    assert adaptador.crear(model="claude-prueba", max_tokens=10) == "respuesta-de-claude"
    assert creados[0].timeout == 12 and creados[0].max_retries == 1
    assert creados[0].llamadas == [{"model": "claude-prueba", "max_tokens": 10}]


def test_sin_el_paquete_anthropic_queda_solo_reglas(monkeypatch: pytest.MonkeyPatch,
                                                    caplog: pytest.LogCaptureFixture) -> None:
    def sin_sdk(_: float) -> Any:
        raise ImportError("No module named 'anthropic'")

    monkeypatch.setattr(modulo_conversador, "_ClienteAnthropic", sin_sdk)
    assert conversador_desde_entorno({"ANTHROPIC_API_KEY": "clave"}) is None
    assert "falta el paquete 'anthropic'" in caplog.text
