import dataclasses

import pytest

from bitcoinai.modelo import Intervalo, Vela


def test_vela_guarda_sus_campos_y_se_compara_por_valor() -> None:
    a = Vela(1000, 10, 12, 9, 11, 5, 1999)
    assert (a.tiempo_apertura, a.apertura, a.maximo, a.minimo, a.cierre, a.volumen, a.tiempo_cierre) == (
        1000, 10, 12, 9, 11, 5, 1999)
    assert a == Vela(1000, 10, 12, 9, 11, 5, 1999)
    assert a != Vela(1000, 10, 12, 9, 11.5, 5, 1999)


def test_vela_es_inmutable() -> None:
    vela = Vela(1000, 10, 12, 9, 11, 5, 1999)
    with pytest.raises(dataclasses.FrozenInstanceError):
        vela.cierre = 20  # type: ignore[misc]


def test_intervalos_tienen_codigo_de_binance_y_duracion() -> None:
    assert Intervalo.M1.codigo == "1m"
    assert Intervalo.M1.milisegundos == 60_000
    assert Intervalo.M5.milisegundos == 300_000
    assert Intervalo.M15.milisegundos == 900_000
    assert Intervalo.H1.milisegundos == 3_600_000
    assert Intervalo.H4.milisegundos == 14_400_000
    assert Intervalo.D1.codigo == "1d"
    assert Intervalo.D1.milisegundos == 86_400_000


def test_desde_codigo_encuentra_cada_intervalo() -> None:
    for intervalo in Intervalo:
        assert Intervalo.desde_codigo(intervalo.codigo) is intervalo


@pytest.mark.parametrize("codigo", ["2h", "1D", "", "d1"])
def test_desde_codigo_rechaza_codigos_desconocidos(codigo: str) -> None:
    with pytest.raises(ValueError, match="Intervalo no soportado"):
        Intervalo.desde_codigo(codigo)
