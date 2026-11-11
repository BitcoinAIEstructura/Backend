"""El chat con Claude, con un cliente falso: nunca se llama a la API real."""

from types import SimpleNamespace
from typing import Any

import pytest

from bitcoinai.asistente.conversador import (
    INSTRUCCIONES,
    MODELO_POR_DEFECTO,
    Conversador,
    Limitador,
    Turno,
    conversador_desde_entorno,
)


class ClienteFalso:
    def __init__(self, texto: str = "Tienes 8.342,14 USDT.", error: Exception | None = None,
                 stop_reason: str = "end_turn") -> None:
        self.texto, self.error, self.stop_reason = texto, error, stop_reason
        self.pedidos: list[dict[str, Any]] = []

    def crear(self, **parametros: Any) -> Any:
        self.pedidos.append(parametros)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(stop_reason=self.stop_reason, content=[
            SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self.texto)])


def test_sin_clave_queda_apagado() -> None:
    assert conversador_desde_entorno({}) is None
    assert conversador_desde_entorno({"ANTHROPIC_API_KEY": "  "}) is None


def test_con_clave_usa_sonnet_por_defecto() -> None:
    c = conversador_desde_entorno({"ANTHROPIC_API_KEY": "clave-de-prueba"})
    assert c is not None and c.modelo == MODELO_POR_DEFECTO == "claude-sonnet-5-5"
    otro = conversador_desde_entorno({"ANTHROPIC_API_KEY": "x", "ASISTENTE_MODELO": "claude-haiku-5-5"})
    assert otro is not None and otro.modelo == "claude-haiku-5-5"


def test_arma_la_peticion_con_instrucciones_en_cache_y_datos_en_el_ultimo_mensaje() -> None:
    cliente = ClienteFalso()
    c = Conversador(cliente)
    historial = (Turno("bot", "¡Hola!"), Turno("usuario", "¿Cómo voy?"), Turno("bot", "Vas bien."))
    assert c.responder(1, "Quiero invertir", historial, "Cartera: vale 10.186,13 USDT.") == "Tienes 8.342,14 USDT."
    p = cliente.pedidos[0]
    assert p["model"] == "claude-sonnet-5-5" and p["output_config"] == {"effort": "low"}
    assert p["system"][0]["text"] == INSTRUCCIONES and p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert p["fallbacks"] == "default" and p["betas"] == ["server-side-fallback-2026-07-01"]
    roles = [m["role"] for m in p["messages"]]
    assert roles == ["user", "assistant", "user"]  # el saludo inicial del bot se omite
    ultimo = p["messages"][-1]["content"]
    assert "<datos_de_practica>" in ultimo and ultimo.endswith("Quiero invertir")
    assert "temperature" not in p and "thinking" not in p


@pytest.mark.parametrize("cliente", [ClienteFalso(error=RuntimeError("sin red")), ClienteFalso(stop_reason="refusal"),
                                     ClienteFalso(texto="  ")])
def test_si_falla_devuelve_none_para_usar_las_reglas(cliente: ClienteFalso) -> None:
    assert Conversador(cliente).responder(1, "hola", (), "datos") is None


def test_limite_por_hora_por_persona() -> None:
    reloj = SimpleNamespace(t=0.0)
    limitador = Limitador(2, ventana_s=3600, reloj=lambda: reloj.t)
    c = Conversador(ClienteFalso(), limitador=limitador)
    assert c.responder(1, "a", (), "d") and c.responder(1, "b", (), "d")
    assert c.responder(1, "c", (), "d") is None  # tercer mensaje en la hora
    assert c.responder(2, "a", (), "d") is not None  # otra persona tiene su propio cupo
    reloj.t = 3600
    assert c.responder(1, "d", (), "d") is not None
