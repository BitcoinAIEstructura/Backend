import pytest

from bitcoinai.modelo import Vela
from bitcoinai.simulacion.si_hubiera import FechaSinDatosError, IndiceVelas

DIA = 86_400_000


def vela(dia: int, apertura: float, maximo: float | None = None, minimo: float | None = None) -> Vela:
    return Vela(dia * DIA, apertura, maximo or apertura, minimo or apertura, apertura, 1.0, (dia + 1) * DIA - 1)


INDICE = IndiceVelas((
    vela(0, 100),
    vela(1, 110, maximo=130),
    vela(2, 90, minimo=80),
    vela(4, 120),  # el día 3 no tiene datos
))


def test_compra_al_abrir_la_vela_de_ese_dia_y_la_valora_hoy() -> None:
    r = INDICE.si_hubiera(1 * DIA, 1000, precio_actual=220, comision=0.001)
    assert r.vela.apertura == 110
    assert r.btc == pytest.approx(999 / 110)
    assert r.valor_hoy == pytest.approx(999 / 110 * 220)
    assert r.ganancia == pytest.approx(r.valor_hoy - 1000)
    assert r.rentabilidad == pytest.approx(r.ganancia / 1000)


def test_una_hora_dentro_del_dia_usa_la_vela_siguiente_con_datos() -> None:
    # A las 10 de la mañana del día 2 ya abrió esa vela: el techo es la del día 4.
    assert INDICE.si_hubiera(2 * DIA + 1, 100, 100).vela.tiempo_apertura == 4 * DIA
    assert INDICE.si_hubiera(3 * DIA, 100, 100).vela.tiempo_apertura == 4 * DIA


def test_mejor_y_peor_momento_solo_desde_esa_fecha() -> None:
    r = INDICE.si_hubiera(1 * DIA, 100, 100)
    assert (r.mejor.tiempo, r.mejor.precio) == (1 * DIA, 130)
    assert (r.peor.tiempo, r.peor.precio) == (2 * DIA, 80)
    assert r.velas_recorridas == 3  # días 1, 2 y 4; el 0 ni se visita
    tarde = INDICE.si_hubiera(4 * DIA, 100, 100)
    assert (tarde.mejor.precio, tarde.peor.precio, tarde.velas_recorridas) == (120, 120, 1)


def test_fechas_sin_datos() -> None:
    with pytest.raises(FechaSinDatosError, match="anterior"):
        INDICE.si_hubiera(-1, 100, 100)
    with pytest.raises(FechaSinDatosError, match="Todavía no hay"):
        INDICE.si_hubiera(5 * DIA, 100, 100)
    with pytest.raises(FechaSinDatosError):
        IndiceVelas(()).si_hubiera(0, 100, 100)


def test_mil_velas_ordenadas_quedan_en_un_arbol_bajo() -> None:
    indice = IndiceVelas(vela(d, 100 + d) for d in range(1000))
    assert indice.arbol.altura() <= 14
    assert (indice.desde(), indice.hasta()) == (0, 999 * DIA)
