import pytest

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import Macd, series
from tests.indicadores.velas_prueba import assert_serie, assert_todos, constantes, de_cierres, lineales


def test_valores_calculados_a_mano_con_periodos_pequenos() -> None:
    # cierres 1..6, rápida 2, lenta 3, señal 2
    # EMA2 (α 2/3): 1,5 2,5 3,5 4,5 5,5 (desde la vela 1)
    # EMA3 (α 1/2): 2 3 4 5 (desde la vela 2)
    # MACD = 0,5 en todas desde la vela 2; señal = 0,5 desde la vela 3; histograma 0
    r = Macd(2, 3, 2).calcular_completo(de_cierres(1, 2, 3, 4, 5, 6))
    assert_serie(r.macd, 2, 0.5, 0.5, 0.5, 0.5)
    assert_serie(r.senal, 3, 0.5, 0.5, 0.5)
    assert_serie(r.histograma, 3, 0, 0, 0)


def test_serie_constante_da_todo_cero() -> None:
    r = Macd().calcular_completo(constantes(60, 100))
    assert r.macd.tamanio() == 35  # 60 − 26 + 1
    assert r.senal.tamanio() == 27  # 35 − 9 + 1
    assert r.histograma.tamanio() == 27
    assert_todos(r.macd, 0)
    assert_todos(r.senal, 0)
    assert_todos(r.histograma, 0)


def test_tendencia_alcista_da_macd_positivo() -> None:
    for punto in Macd().calcular_completo(lineales(80, 100, 2)).macd:
        assert punto.valor > 0


def test_histograma_es_macd_menos_senal_en_el_mismo_tiempo() -> None:
    r = Macd(3, 6, 3).calcular_completo(de_cierres(5, 7, 6, 9, 12, 10, 8, 11, 15, 14, 13, 16))
    macd_alineado = series.ultimos(r.macd, r.senal.tamanio())
    for h, m, s in zip(r.histograma, macd_alineado, r.senal, strict=True):
        assert m.tiempo == h.tiempo == s.tiempo
        assert h.valor == pytest.approx(m.valor - s.valor, abs=1e-12)


def test_calcular_series_devuelve_las_tres_con_nombre() -> None:
    velas = lineales(50, 1, 1)
    resultado = Macd().calcular_series(velas)
    assert tuple(resultado) == ("macd", "senal", "histograma")
    assert resultado["macd"].tamanio() == Macd().calcular(velas).tamanio()


def test_pocas_velas_dan_series_vacias() -> None:
    r = Macd().calcular_completo(de_cierres(1, 2, 3))
    assert r.macd.esta_vacia() and r.senal.esta_vacia() and r.histograma.esta_vacia()
    assert Macd().calcular(ListaDoble()).esta_vacia()
    assert Macd(2, 3, 2).calcular(de_cierres(5)).esta_vacia()


def test_parametros_invalidos() -> None:
    with pytest.raises(ValueError):
        Macd(26, 12, 9)
    with pytest.raises(ValueError):
        Macd(12, 12, 9)
    with pytest.raises(ValueError):
        Macd(12, 26, 0)
    assert Macd().parametros() == {"rapido": 12, "lento": 26, "senal": 9}
