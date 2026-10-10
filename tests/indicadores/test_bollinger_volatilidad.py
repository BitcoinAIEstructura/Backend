import math

import pytest

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import BandasBollinger, Sma, Volatilidad
from tests.indicadores.velas_prueba import assert_serie, assert_todos, constantes, de_cierres

# ---------- Bollinger ----------


def test_serie_constante_tiene_bandas_iguales_a_la_media() -> None:
    b = BandasBollinger(20, 2).calcular_bandas(constantes(30, 85_000.5))
    assert b.media.tamanio() == 11
    assert_todos(b.media, 85_000.5)
    assert_todos(b.superior, 85_000.5)
    assert_todos(b.inferior, 85_000.5)


def test_valores_calculados_a_mano() -> None:
    # periodo 2, k 2, cierres 1,3,5
    # [1,3]: media 2, σ = 1 → 4 y 0;  [3,5]: media 4, σ = 1 → 6 y 2
    b = BandasBollinger(2, 2).calcular_bandas(de_cierres(1, 3, 5))
    assert_serie(b.media, 1, 2, 4)
    assert_serie(b.superior, 1, 4, 6)
    assert_serie(b.inferior, 1, 0, 2)


def test_media_coincide_con_la_sma_y_las_bandas_son_simetricas() -> None:
    velas = de_cierres(85_010, 84_950, 85_200, 84_700, 85_500, 85_100, 84_900, 85_300)
    b = BandasBollinger(4, 2).calcular_bandas(velas)
    for media, sma, sup, inf in zip(b.media, Sma(4).calcular(velas), b.superior, b.inferior, strict=True):
        assert media.valor == pytest.approx(sma.valor, abs=1e-6)
        arriba = sup.valor - media.valor
        abajo = media.valor - inf.valor
        assert arriba == pytest.approx(abajo, abs=1e-6)
        assert arriba > 0


def test_bollinger_con_serie_vacia_y_un_elemento() -> None:
    assert BandasBollinger(20, 2).calcular(ListaDoble()).esta_vacia()
    assert BandasBollinger(2, 2).calcular(de_cierres(5)).esta_vacia()
    assert_serie(BandasBollinger(1, 2).calcular_bandas(de_cierres(5)).superior, 0, 5)
    assert tuple(BandasBollinger(2, 2).calcular_series(de_cierres(1, 2))) == ("media", "superior", "inferior")


def test_bollinger_parametros_invalidos() -> None:
    with pytest.raises(ValueError):
        BandasBollinger(0, 2)
    with pytest.raises(ValueError):
        BandasBollinger(20, 0)
    with pytest.raises(ValueError):
        BandasBollinger(20, math.nan)


# ---------- Volatilidad ----------


def test_precios_constantes_tienen_volatilidad_cero() -> None:
    v = Volatilidad(5).calcular(constantes(10, 100))
    assert v.tamanio() == 5
    assert_todos(v, 0)


def test_volatilidad_calculada_a_mano() -> None:
    # cierres 1, e, e³ → retornos ln(e) = 1 y ln(e²) = 2
    # media 1,5; desviación muestral √(((1−1,5)² + (2−1,5)²) / 1) = √0,5
    assert_serie(Volatilidad(2).calcular(de_cierres(1, math.e, math.exp(3))), 2, math.sqrt(0.5))


def test_crecimiento_porcentual_constante_tiene_volatilidad_cero() -> None:
    cierres = tuple(100 * 1.01**i for i in range(15))  # cada cierre 1 % mayor que el anterior
    for punto in Volatilidad(5).calcular(de_cierres(*cierres)):
        assert punto.valor == pytest.approx(0, abs=1e-9)


def test_volatilidad_con_serie_vacia_un_elemento_y_pocas_velas() -> None:
    assert Volatilidad(3).calcular(ListaDoble()).esta_vacia()
    assert Volatilidad(3).calcular(de_cierres(5)).esta_vacia()
    assert Volatilidad(3).calcular(de_cierres(1, 2, 3)).esta_vacia()
    assert Volatilidad(3).calcular(de_cierres(1, 2, 3, 4)).tamanio() == 1
    with pytest.raises(ValueError):
        Volatilidad(1)
