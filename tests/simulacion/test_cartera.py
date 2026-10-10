import pytest

from bitcoinai.simulacion import Cartera, OperacionRechazadaError

C = 0.001


def test_empieza_con_diez_mil_usdt_y_sin_btc() -> None:
    cartera = Cartera()
    assert (cartera.saldo_usdt, cartera.btc, cartera.costo_promedio()) == (10_000, 0, 0)
    assert cartera.valor_total(85_000) == 10_000
    assert cartera.ganancia_total(85_000) == 0


def test_compra_descuenta_el_saldo_y_cobra_comision() -> None:
    cartera = Cartera()
    e = cartera.comprar(500, 100, C)
    assert e.monto_usdt == 500
    assert e.comision == pytest.approx(0.5)
    assert e.cantidad_btc == pytest.approx(4.995)
    assert cartera.saldo_usdt == pytest.approx(9_500)
    assert cartera.btc == pytest.approx(4.995)
    assert cartera.costo_promedio() == pytest.approx(500 / 4.995)  # la comisión forma parte del costo


def test_venta_de_todo_realiza_la_ganancia() -> None:
    cartera = Cartera()
    cartera.comprar(500, 100, C)
    e = cartera.vender_todo(110, C)
    bruto = 4.995 * 110
    assert e.monto_usdt == pytest.approx(bruto)
    assert e.comision == pytest.approx(bruto * C)
    assert (cartera.btc, cartera.costo_promedio()) == (0, 0)
    assert cartera.saldo_usdt == pytest.approx(9_500 + bruto * (1 - C))
    estado = cartera.estado(110)
    assert estado.ganancia_realizada == pytest.approx(bruto * (1 - C) - 500)
    assert estado.ganancia_total == pytest.approx(estado.ganancia_realizada)
    assert estado.comisiones_pagadas == pytest.approx(0.5 + bruto * C)


def test_venta_parcial_conserva_el_costo_promedio() -> None:
    cartera = Cartera()
    cartera.comprar(1000, 100, 0)  # 10 BTC a 100
    cartera.vender(300, 150, 0)  # vende 2 BTC
    assert cartera.btc == pytest.approx(8)
    assert cartera.costo_promedio() == pytest.approx(100)
    assert cartera.estado(150).ganancia_realizada == pytest.approx(100)  # 300 − 2·100
    assert cartera.ganancia_no_realizada(150) == pytest.approx(400)  # 8·150 − 800


def test_dos_compras_promedian_el_costo() -> None:
    cartera = Cartera()
    cartera.comprar(1000, 100, 0)  # 10 BTC
    cartera.comprar(1000, 200, 0)  # 5 BTC
    assert cartera.btc == pytest.approx(15)
    assert cartera.costo_promedio() == pytest.approx(2000 / 15)


def test_rechaza_compra_sin_saldo_y_venta_sin_btc() -> None:
    cartera = Cartera(1000)
    mensaje = r"^Saldo insuficiente: la compra necesita 1500\.00 USDT y hay 1000\.00$"
    with pytest.raises(OperacionRechazadaError, match=mensaje):
        cartera.comprar(1500, 100, C)
    with pytest.raises(OperacionRechazadaError):
        cartera.vender(10, 100, C)
    with pytest.raises(OperacionRechazadaError, match="No hay BTC para vender"):
        cartera.vender_todo(100, C)
    assert cartera.saldo_usdt == 1000  # nada cambió


def test_puede_gastar_todo_el_saldo_exacto() -> None:
    cartera = Cartera(1000)
    cartera.comprar(1000, 100, C)
    assert cartera.saldo_usdt == 0
    assert cartera.btc > 0


def test_saldo_inicial_invalido() -> None:
    for saldo in (0, -5):
        with pytest.raises(ValueError):
            Cartera(saldo)
