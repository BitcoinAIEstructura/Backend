import pytest

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import (
    PuntoIndicador,
    ResultadoCaida,
    maxima_caida_de_puntos,
    maxima_caida_de_velas,
    series,
)
from tests.indicadores.velas_prueba import PASO, assert_serie, de_cierres, lineales

# ---------- máxima caída ----------


def test_encuentra_la_peor_caida_aunque_haya_otras_despues() -> None:
    # 120 → 90 es −25 %; luego 130 → 104 es −20 %
    r = maxima_caida_de_velas(de_cierres(100, 120, 90, 130, 104))
    assert r.caida_maxima == pytest.approx(0.25)
    assert (r.valor_pico, r.tiempo_pico, r.valor_valle, r.tiempo_valle) == (120, PASO, 90, 2 * PASO)


def test_caida_que_sigue_bajando_toma_el_punto_mas_bajo() -> None:
    r = maxima_caida_de_velas(de_cierres(100, 80, 60, 70, 50, 90))
    assert r.caida_maxima == pytest.approx(0.5)
    assert (r.valor_pico, r.valor_valle) == (100, 50)


def test_serie_que_solo_sube_no_tiene_caida() -> None:
    r = maxima_caida_de_velas(lineales(10, 1, 1))
    assert (r.caida_maxima, r.valor_pico, r.valor_valle) == (0, 1, 1)


def test_serie_vacia_y_de_un_elemento() -> None:
    assert maxima_caida_de_velas(ListaDoble()) == ResultadoCaida(0, 0, 0, 0, 0)
    assert maxima_caida_de_puntos(None) == ResultadoCaida(0, 0, 0, 0, 0)
    assert maxima_caida_de_velas(de_cierres(7)) == ResultadoCaida(0, 0, 7, 0, 7)


def test_funciona_con_puntos_de_capital() -> None:
    capital: ListaDoble[PuntoIndicador] = ListaDoble()
    for t, v in ((1, 1000), (2, 900), (3, 1100)):
        capital.agregar_final(PuntoIndicador(t, v))
    assert maxima_caida_de_puntos(capital).caida_maxima == pytest.approx(0.1)


# ---------- series ----------


def uno_a_diez() -> ListaDoble[int]:
    lista: ListaDoble[int] = ListaDoble()
    for i in range(1, 11):
        lista.agregar_final(i)
    return lista


def test_cierres_convierte_velas_en_puntos() -> None:
    assert_serie(series.cierres(de_cierres(3, 1, 4)), 0, 3, 1, 4)
    assert series.cierres(None).esta_vacia()


def test_ultimos_devuelve_los_mas_recientes_en_orden_cronologico() -> None:
    assert tuple(series.ultimos(uno_a_diez(), 3)) == (8, 9, 10)


def test_ultimos_con_mas_de_los_que_hay_o_cero() -> None:
    assert series.ultimos(uno_a_diez(), 50).tamanio() == 10
    assert series.ultimos(uno_a_diez(), 0).esta_vacia()
    assert series.ultimos(ListaDoble[int](), 3).esta_vacia()
    with pytest.raises(ValueError):
        series.ultimos(uno_a_diez(), -1)


def test_ultimos_no_modifica_la_original() -> None:
    original = uno_a_diez()
    series.ultimos(original, 4).vaciar()
    assert original.tamanio() == 10


def test_ema_de_una_serie_de_puntos() -> None:
    assert_serie(series.ema(series.cierres(de_cierres(1, 2, 3, 4, 5)), 3), 2, 2, 3, 4)
    with pytest.raises(ValueError):
        series.ema(ListaDoble(), 0)
