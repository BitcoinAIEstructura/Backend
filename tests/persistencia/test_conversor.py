"""Los caminos de error del conversor: un archivo guardado con datos imposibles se rechaza.

Cada campo que llega del disco se valida al convertirlo; estas pruebas fijan el mensaje
de cada rechazo para que un archivo dañado nunca se cuele como estado válido.
"""

import math

import pytest

from bitcoinai.persistencia.conversor import (
    DatosDanadosError,
    booleano,
    cartera,
    entero,
    entero_opcional,
    enumerado,
    evento,
    lista,
    mapa,
    numero,
    numero_opcional,
    orden,
    texto,
    texto_opcional,
)
from bitcoinai.simulacion import EstadoOrden, TipoEvento, TipoOrden

# ---------- utilidades de campo ----------


def test_mapa_exige_un_objeto() -> None:
    with pytest.raises(DatosDanadosError, match="se esperaba un objeto en cartera"):
        mapa(["no", "es", "un", "objeto"], "cartera")


def test_lista_exige_una_lista() -> None:
    with pytest.raises(DatosDanadosError, match="falta la lista 'creadas'"):
        lista({}, "creadas")
    with pytest.raises(DatosDanadosError, match="falta la lista 'creadas'"):
        lista({"creadas": "1,2,3"}, "creadas")


def test_numero_obligatorio() -> None:
    with pytest.raises(DatosDanadosError, match="falta el número 'saldoInicial'"):
        numero({}, "saldoInicial")
    with pytest.raises(DatosDanadosError, match="falta el número 'saldoInicial'"):
        numero({"saldoInicial": None}, "saldoInicial")


@pytest.mark.parametrize("valor", [True, False, "1000", [1], {"a": 1}])
def test_numero_opcional_rechaza_lo_que_no_es_numero(valor: object) -> None:
    with pytest.raises(DatosDanadosError, match="debe ser un número"):
        numero_opcional({"x": valor}, "x")


@pytest.mark.parametrize("valor", [math.inf, -math.inf, math.nan])
def test_numero_opcional_rechaza_infinitos_y_nan(valor: float) -> None:
    with pytest.raises(DatosDanadosError, match="debe ser un número"):
        numero_opcional({"x": valor}, "x")


def test_numero_opcional_acepta_enteros_y_devuelve_float() -> None:
    valor = numero_opcional({"x": 3}, "x")
    assert valor == 3.0 and isinstance(valor, float)
    assert numero_opcional({}, "x") is None


def test_entero_opcional_rechaza_fraccionarios() -> None:
    with pytest.raises(DatosDanadosError, match="debe ser un entero"):
        entero_opcional({"x": 1.5}, "x")


def test_entero_obligatorio() -> None:
    assert entero({"x": 7.0}, "x") == 7
    with pytest.raises(DatosDanadosError, match="falta el entero 'x'"):
        entero({}, "x")


def test_texto_rechaza_lo_que_no_es_texto() -> None:
    with pytest.raises(DatosDanadosError, match="debe ser un texto"):
        texto_opcional({"x": 12}, "x")
    with pytest.raises(DatosDanadosError, match="falta el texto 'motivo'"):
        texto({}, "motivo")
    assert texto({"motivo": ""}, "motivo") == ""


def test_booleano_exige_true_o_false() -> None:
    assert booleano({"x": True}, "x") is True
    with pytest.raises(DatosDanadosError, match="debe ser true o false"):
        booleano({"x": "si"}, "x")
    with pytest.raises(DatosDanadosError, match="debe ser true o false"):
        booleano({}, "x")


def test_enumerado_con_nombre_desconocido() -> None:
    assert enumerado({"tipo": "COMPRA"}, "tipo", TipoOrden) is TipoOrden.COMPRA
    with pytest.raises(DatosDanadosError, match="valor desconocido en 'tipo': REGALADA"):
        enumerado({"tipo": "REGALADA"}, "tipo", TipoOrden)


# ---------- cartera ----------


def test_cartera_valida() -> None:
    datos = cartera({"saldoInicial": 10_000, "saldoUsdt": 9_000, "btc": 0.01, "costoPosicion": 500,
                     "gananciaRealizada": 0, "comisionesPagadas": 1.5})
    assert datos.saldo_inicial == 10_000 and datos.comisiones_pagadas == 1.5


def test_cartera_con_valores_imposibles() -> None:
    with pytest.raises(DatosDanadosError, match="cartera con valores imposibles"):
        cartera({"saldoInicial": -1, "saldoUsdt": 0, "btc": 0, "costoPosicion": 0,
                 "gananciaRealizada": 0, "comisionesPagadas": 0})


def test_cartera_que_no_es_objeto() -> None:
    with pytest.raises(DatosDanadosError, match="se esperaba un objeto en cartera"):
        cartera("10.000 USDT")


# ---------- orden ----------


def orden_valida(**cambios: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 1, "tipo": "COMPRA", "monto": 500.0, "todo": False, "estado": "PENDIENTE", "creadaEn": 10,
        "ejecutadaEn": None, "precioEjecucion": None, "cantidadBtc": None, "comision": None,
        "motivo": "manual", "detalle": None,
    }
    base.update(cambios)
    return base


def test_orden_valida() -> None:
    o = orden(orden_valida())
    assert (o.id, o.tipo, o.monto, o.estado) == (1, TipoOrden.COMPRA, 500.0, EstadoOrden.PENDIENTE)


@pytest.mark.parametrize("datos", [
    orden_valida(id=0),
    orden_valida(id=-3),
    orden_valida(tipo="COMPRA", todo=True),          # "todo" solo vale en una venta
    orden_valida(monto=None, todo=False),            # una compra necesita monto
])
def test_orden_incoherente(datos: dict[str, object]) -> None:
    with pytest.raises(DatosDanadosError, match="datos incoherentes"):
        orden(datos)


def test_venta_de_todo_sin_monto_es_valida() -> None:
    o = orden(orden_valida(tipo="VENTA", todo=True, monto=None))
    assert o.todo is True and o.monto is None


# ---------- evento ----------


def test_evento_valido_y_su_error() -> None:
    e = evento({"momento": 5, "tipo": "DECISION_BOT", "idOrden": None, "descripcion": "esperó"})
    assert (e.momento, e.tipo, e.descripcion) == (5, TipoEvento.DECISION_BOT, "esperó")
    with pytest.raises(DatosDanadosError, match="falta el texto 'descripcion'"):
        evento({"momento": 5, "tipo": "DECISION_BOT", "idOrden": None})
