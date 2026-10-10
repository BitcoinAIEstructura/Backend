import pytest

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import Rsi
from tests.indicadores.velas_prueba import assert_serie, assert_todos, constantes, de_cierres, lineales


def test_serie_plana_da_cincuenta() -> None:
    rsi = Rsi(14).calcular(constantes(30, 100))
    assert rsi.tamanio() == 16  # 30 velas − 14
    assert_todos(rsi, 50)


def test_serie_siempre_creciente_da_cien() -> None:
    rsi = Rsi(14).calcular(lineales(40, 100, 3))
    assert rsi.tamanio() == 26
    assert_todos(rsi, 100)


def test_serie_siempre_decreciente_da_cero() -> None:
    assert_todos(Rsi(5).calcular(lineales(20, 100, -2)), 0)


def test_valores_calculados_a_mano_con_suavizado_de_wilder() -> None:
    # cierres 1,2,1,2,3 → cambios +1,−1,+1,+1; periodo 2
    # inicio: ganancia (1+0)/2 = 0,5; pérdida (0+1)/2 = 0,5 → RS 1 → RSI 50
    # +1: ganancia (0,5·1+1)/2 = 0,75; pérdida (0,5·1+0)/2 = 0,25 → RS 3 → RSI 75
    # +1: ganancia (0,75+1)/2 = 0,875; pérdida 0,125 → RS 7 → RSI 87,5
    assert_serie(Rsi(2).calcular(de_cierres(1, 2, 1, 2, 3)), 2, 50, 75, 87.5)


def test_primer_punto_necesita_periodo_mas_una_vela() -> None:
    assert Rsi(3).calcular(de_cierres(1, 2, 3)).esta_vacia()
    assert Rsi(3).calcular(de_cierres(1, 2, 3, 4)).tamanio() == 1


def test_siempre_entre_cero_y_cien() -> None:
    for punto in Rsi(3).calcular(de_cierres(10, 13, 9, 15, 8, 8, 20, 1, 7)):
        assert 0 <= punto.valor <= 100


def test_serie_vacia_y_de_un_elemento() -> None:
    assert Rsi(14).calcular(ListaDoble()).esta_vacia()
    assert Rsi(14).calcular(de_cierres(5)).esta_vacia()
    assert Rsi(1).calcular(de_cierres(5)).esta_vacia()


def test_periodo_invalido() -> None:
    with pytest.raises(ValueError):
        Rsi(0)
