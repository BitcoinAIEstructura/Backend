"""Las propuestas de la IA del chat: el servidor solo deja pasar las que tienen sentido."""

import dataclasses

import pytest

from bitcoinai.asistente.asistente import AlertaPropuesta, OrdenPropuesta
from bitcoinai.asistente.propuestas import HERRAMIENTAS, NOMBRES, PAGINAS, validar
from tests.asistente.test_asistente import bot, cartera, datos


def con_btc() -> object:
    """10.000 USDT libres y 0,05 BTC que valen 3.000 USDT, a 60.000,50."""
    return dataclasses.replace(cartera(), btc=0.05, valor_btc=3000.0)


def test_las_herramientas_son_estrictas_y_coinciden_con_los_nombres() -> None:
    assert {h["name"] for h in HERRAMIENTAS} == NOMBRES
    for h in HERRAMIENTAS:
        esquema = h["input_schema"]
        assert h["strict"] is True and esquema["additionalProperties"] is False
        assert set(esquema["required"]) == set(esquema["properties"])


def test_compra_que_alcanza_redondea_hacia_abajo_y_la_etiqueta_es_del_servidor() -> None:
    a = validar("proponer_orden", {"tipo": "COMPRA", "monto_usdt": 1999.999, "vender_todo": False}, datos(), False)
    assert a is not None and a.tipo == "ORDEN"
    assert a.orden == OrdenPropuesta("COMPRA", 1999.99) and a.etiqueta == "Comprar 1.999,99 USDT de BTC"


@pytest.mark.parametrize("monto", [0, 0.5, -10, 10_000.01, float("nan"), float("inf"), "500", True, None])
def test_compra_invalida_se_descarta(monto: object) -> None:
    assert validar("proponer_orden", {"tipo": "COMPRA", "monto_usdt": monto, "vender_todo": False},
                   datos(), False) is None


def test_compra_sin_precio_se_descarta() -> None:
    assert validar("proponer_orden", {"tipo": "COMPRA", "monto_usdt": 100, "vender_todo": False},
                   datos(cartera=None), False) is None


def test_venta_hasta_el_valor_del_btc_o_todo() -> None:
    d = datos(cartera=con_btc())
    parcial = validar("proponer_orden", {"tipo": "VENTA", "monto_usdt": 1500, "vender_todo": False}, d, False)
    assert parcial is not None and parcial.orden == OrdenPropuesta("VENTA", 1500.0)
    assert validar("proponer_orden", {"tipo": "VENTA", "monto_usdt": 3000.01, "vender_todo": False}, d, False) is None
    todo = validar("proponer_orden", {"tipo": "VENTA", "monto_usdt": None, "vender_todo": True}, d, False)
    assert todo is not None and todo.orden == OrdenPropuesta("VENTA", None, todo=True)
    assert "Vender todo mi BTC" in todo.etiqueta


def test_no_vende_lo_que_no_tiene() -> None:
    assert validar("proponer_orden", {"tipo": "VENTA", "monto_usdt": None, "vender_todo": True}, datos(), False) is None
    assert validar("proponer_orden", {"tipo": "VENTA", "monto_usdt": 10, "vender_todo": False}, datos(), False) is None


def test_bot_encender_y_detener_segun_su_estado() -> None:
    apagado, encendido = datos(), datos(bot=bot(activo=True))
    ia = validar("proponer_bot", {"accion": "ENCENDER", "modo": "ia"}, apagado, True)
    assert ia is not None and ia.tipo == "INICIAR_BOT" and ia.modo == "ia"
    assert validar("proponer_bot", {"accion": "ENCENDER", "modo": "ia"}, apagado, False) is None  # sin piloto
    actual = validar("proponer_bot", {"accion": "ENCENDER", "modo": "actual"}, apagado, False)
    assert actual is not None and actual.modo is None
    assert validar("proponer_bot", {"accion": "ENCENDER", "modo": "reglas"}, encendido, True) is None
    detener = validar("proponer_bot", {"accion": "DETENER", "modo": "actual"}, encendido, True)
    assert detener is not None and detener.tipo == "DETENER_BOT"
    assert validar("proponer_bot", {"accion": "DETENER", "modo": "actual"}, apagado, True) is None


def test_alerta_por_encima_o_por_debajo_del_precio() -> None:
    sube = validar("proponer_alerta", {"tipo": "SUBE_A", "precio": 65_000}, datos(), False)
    assert sube is not None and sube.alerta == AlertaPropuesta("SUBE_A", 65_000.0)
    baja = validar("proponer_alerta", {"tipo": "BAJA_A", "precio": 55_000.456}, datos(), False)
    assert baja is not None and baja.alerta == AlertaPropuesta("BAJA_A", 55_000.46)
    assert validar("proponer_alerta", {"tipo": "SUBE_A", "precio": 50_000}, datos(), False) is None
    assert validar("proponer_alerta", {"tipo": "BAJA_A", "precio": 70_000}, datos(), False) is None


def test_paginas_solo_las_conocidas() -> None:
    for clave, (ruta, _) in PAGINAS.items():
        a = validar("proponer_pagina", {"pagina": clave}, datos(), False)
        assert a is not None and a.tipo == "IR" and a.ruta == ruta
    assert validar("proponer_pagina", {"pagina": "https://otro.sitio"}, datos(), False) is None
    assert validar("borrar_todo", {}, datos(), False) is None
