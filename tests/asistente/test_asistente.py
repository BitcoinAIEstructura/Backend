import pytest

from bitcoinai.asistente import Asistente, DatosUsuario
from bitcoinai.asistente import intenciones as i
from bitcoinai.asistente.asistente import duracion, usdt
from bitcoinai.estrategia import Decision, Senal
from bitcoinai.simulacion import ConfiguracionBot, EstadoBot, EstadoCartera

AHORA = 1_000_000_000


def bot(activo: bool = False, **cambios: object) -> EstadoBot:
    base: dict[str, object] = {
        "activo": activo, "estrategia": "combinada", "configuracion": ConfiguracionBot(), "ciclos": 0,
        "ultimo_ciclo": None, "ultima_decision": None, "ultimo_error": None,
        "encendido_desde": AHORA - 125_000 if activo else None, "en_ciclo": False,
    }
    base.update(cambios)
    return EstadoBot(**base)  # type: ignore[arg-type]


def cartera(ganancia: float = 0.0, btc: float = 0.0) -> EstadoCartera:
    return EstadoCartera(precio_actual=60_000.5, saldo_usdt=10_000 + ganancia, btc=btc, costo_promedio=0,
                         valor_btc=0, valor_total=10_000 + ganancia, ganancia_no_realizada=0,
                         ganancia_realizada=ganancia, ganancia_total=ganancia, rentabilidad=ganancia / 10_000,
                         comisiones_pagadas=0, saldo_inicial=10_000)


def datos(**cambios: object) -> DatosUsuario:
    base: dict[str, object] = {"cartera": cartera(), "bot": bot(), "pendientes": 0}
    base.update(cambios)
    return DatosUsuario(**base)  # type: ignore[arg-type]


@pytest.fixture
def asistente() -> Asistente:
    return Asistente(reloj=lambda: AHORA)


@pytest.mark.parametrize(("mensaje", "intencion"), [
    ("Hola", i.SALUDO),
    ("¿Qué estás haciendo?", i.ESTADO_BOT),
    ("¿está encendido el bot?", i.ESTADO_BOT),  # "encendido" gana a la raíz "encend"
    ("enciende el bot", i.INICIAR_BOT),
    ("Enciéndete por favor", i.INICIAR_BOT),
    ("INICIA", i.INICIAR_BOT),
    ("para el bot", i.DETENER_BOT),
    ("detente", i.DETENER_BOT),
    ("apágate", i.DETENER_BOT),
    ("¿Por qué compraste?", i.POR_QUE),
    ("por que decidiste eso", i.POR_QUE),
    ("¿Cuánto he ganado?", i.GANANCIA),
    ("cuanto dinero tengo", i.GANANCIA),
    ("¿Cuánto cuesta el Bitcoin?", i.PRECIO),
    ("¿tengo órdenes pendientes?", i.ORDENES),
    ("¿Qué dice la IA?", i.IA),
    ("¿qué es el stop loss?", "concepto:stop-loss"),
    ("que es take profit", "concepto:take-profit"),
    ("¿Qué es el RSI?", "concepto:rsi"),
    ("explícame las velas", "concepto:vela"),
    ("¿es dinero real?", "concepto:simulado"),
    ("gracias", i.GRACIAS),
    ("asdfgh qwerty", i.NO_ENTENDI),
    ("", i.NO_ENTENDI),
    ("ia", i.IA),
    ("iapqwe", i.NO_ENTENDI),  # una raíz de 2 letras solo cuenta si es la palabra entera
])
def test_entiende_la_intencion(asistente: Asistente, mensaje: str, intencion: str) -> None:
    assert asistente.entender(mensaje) == intencion


def test_pedir_encenderlo_devuelve_una_accion_y_no_lo_enciende(asistente: Asistente) -> None:
    r = asistente.responder("enciéndete", datos())
    assert r.accion is not None and r.accion.tipo == "INICIAR_BOT"
    assert "cada minuto" in r.texto and "20 %" in r.texto
    ya = asistente.responder("enciéndete", datos(bot=bot(activo=True)))
    assert ya.accion is None and ya.texto.startswith("Ya estoy encendido")


def test_detener_solo_ofrece_la_accion_si_esta_encendido(asistente: Asistente) -> None:
    accion = asistente.responder("detente", datos(bot=bot(activo=True))).accion
    assert accion is not None and accion.tipo == "DETENER_BOT"
    assert asistente.responder("detente", datos()).accion is None


def test_el_estado_cuenta_cuanto_lleva_y_cuando_es_la_proxima(asistente: Asistente) -> None:
    decision = Decision(0, Senal.COMPRAR, 60_000, 0.67, "Votación ponderada: …")
    estado = bot(activo=True, ciclos=3, ultimo_ciclo=AHORA - 20_000, ultima_decision=decision)
    texto = asistente.responder("¿qué haces?", datos(bot=estado)).texto
    assert "desde hace 2 min" in texto and "3 veces" in texto
    assert "La próxima revisión es en 40 s" in texto and "decidí fue comprar" in texto
    revisando = asistente.responder("estado", datos(bot=bot(activo=True, en_ciclo=True))).texto
    assert "Justo ahora lo estoy revisando" in revisando


def test_por_que_explica_la_ultima_decision(asistente: Asistente) -> None:
    sin = asistente.responder("¿por qué?", datos()).texto
    assert "Todavía no he decidido" in sin
    decision = Decision(0, Senal.MANTENER, 61_234.5, 0.5, "Votación ponderada: gana MANTENER.")
    texto = asistente.responder("¿por qué?", datos(bot=bot(ultima_decision=decision))).texto
    assert "Decidí esperar" in texto and "50 %" in texto and "61.234,50 USDT" in texto


def test_ganancia_en_palabras(asistente: Asistente) -> None:
    gano = asistente.responder("¿cuánto he ganado?", datos(cartera=cartera(ganancia=151))).texto
    assert "Vas ganando 151,00 USDT (1,51 %)" in gano and "10.151,00 USDT en total" in gano
    perdio = asistente.responder("¿cuánto he ganado?", datos(cartera=cartera(ganancia=-20))).texto
    assert "Vas perdiendo 20,00 USDT" in perdio
    assert "ni ganas ni pierdes" in asistente.responder("mi cartera", datos()).texto
    assert "no pude leer el precio" in asistente.responder("mi saldo", datos(cartera=None)).texto


def test_precio_y_ordenes(asistente: Asistente) -> None:
    assert "60.000,50 USDT" in asistente.responder("precio", datos()).texto
    assert "2 órdenes esperan" in asistente.responder("ordenes", datos(pendientes=2)).texto
    assert "No tienes órdenes" in asistente.responder("ordenes", datos()).texto


def test_siempre_hay_sugerencias(asistente: Asistente) -> None:
    for mensaje in ("hola", "xyz", "rsi", "precio"):
        assert len(asistente.responder(mensaje, datos()).sugerencias) >= 2


def test_formatos() -> None:
    assert usdt(1234.5) == "1.234,50"
    assert (duracion(45_000), duracion(180_000), duracion(7_500_000), duracion(-5)) == (
        "45 s", "3 min", "2 h 5 min", "0 s")
