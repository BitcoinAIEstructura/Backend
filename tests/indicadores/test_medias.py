import pytest

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import Ema, Sma
from tests.indicadores.velas_prueba import assert_serie, de_cierres, lineales

# ---------- SMA ----------


def test_sma_de_uno_a_cinco_con_periodo_tres() -> None:
    # (1+2+3)/3 = 2, (2+3+4)/3 = 3, (3+4+5)/3 = 4; el primer punto es la vela 2
    assert_serie(Sma(3).calcular(de_cierres(1, 2, 3, 4, 5)), 2, 2, 3, 4)


def test_sma_con_periodo_uno_es_el_precio() -> None:
    assert_serie(Sma(1).calcular(de_cierres(7, 3, 9)), 0, 7, 3, 9)


def test_sma_con_ventana_deslizante_larga() -> None:
    # 1..10 con periodo 4: medias 2.5, 3.5, ..., 8.5
    assert_serie(Sma(4).calcular(lineales(10, 1, 1)), 3, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5)


def test_sma_con_serie_vacia_un_elemento_o_periodo_mayor() -> None:
    assert Sma(3).calcular(ListaDoble()).esta_vacia()
    assert Sma(3).calcular(None).esta_vacia()
    assert Sma(2).calcular(de_cierres(5)).esta_vacia()
    assert_serie(Sma(1).calcular(de_cierres(5)), 0, 5)
    assert Sma(10).calcular(de_cierres(1, 2, 3)).esta_vacia()


def test_sma_no_modifica_las_velas_de_entrada() -> None:
    velas = de_cierres(1, 2, 3, 4)
    Sma(2).calcular(velas)
    assert velas.tamanio() == 4


# ---------- EMA ----------


def test_ema_con_periodo_uno_es_igual_al_precio() -> None:
    assert_serie(Ema(1).calcular(de_cierres(10, 12, 11, 15, 14)), 0, 10, 12, 11, 15, 14)


def test_ema_se_inicializa_con_la_sma_y_luego_suaviza() -> None:
    # α = 2/(3+1) = 0,5; EMA₀ = (1+2+3)/3 = 2; luego 0,5·4 + 0,5·2 = 3; 0,5·5 + 0,5·3 = 4
    assert_serie(Ema(3).calcular(de_cierres(1, 2, 3, 4, 5)), 2, 2, 3, 4)


def test_ema_con_periodo_dos() -> None:
    # α = 2/3; EMA₀ = (2+4)/2 = 3; 2/3·6 + 1/3·3 = 5; 2/3·8 + 1/3·5 = 7; luego 9 y 11
    assert_serie(Ema(2).calcular(de_cierres(2, 4, 6, 8, 10, 12)), 1, 3, 5, 7, 9, 11)


def test_ema_reacciona_mas_rapido_que_la_sma() -> None:
    velas = de_cierres(10, 10, 10, 10, 20)
    assert Ema(4).calcular(velas).ultimo().valor == pytest.approx(14.0)  # 0,4·20 + 0,6·10
    assert Sma(4).calcular(velas).ultimo().valor == pytest.approx(12.5)


def test_ema_con_serie_vacia_y_un_elemento() -> None:
    assert Ema(3).calcular(ListaDoble()).esta_vacia()
    assert Ema(3).calcular(de_cierres(5)).esta_vacia()
    assert_serie(Ema(1).calcular(de_cierres(5)), 0, 5)


def test_periodos_invalidos_en_el_constructor() -> None:
    with pytest.raises(ValueError):
        Sma(0)
    with pytest.raises(ValueError):
        Ema(-1)
