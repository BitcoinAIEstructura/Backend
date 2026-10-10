import math

import pytest

from bitcoinai.estructuras import ListaDoble
from bitcoinai.mercado import MercadoError, validar_velas, velas_cerradas
from bitcoinai.modelo import Intervalo, Vela
from tests.apoyo.fuente_falsa import generar_velas


def vela(tiempo: int, apertura: float, maximo: float, minimo: float, cierre: float, volumen: float) -> Vela:
    return Vela(tiempo, apertura, maximo, minimo, cierre, volumen, tiempo + 59_999)


def lista_de(*velas: Vela) -> ListaDoble[Vela]:
    lista: ListaDoble[Vela] = ListaDoble()
    for v in velas:
        lista.agregar_final(v)
    return lista


def assert_invalida(fragmento: str, *velas: Vela) -> None:
    with pytest.raises(MercadoError) as error:
        validar_velas(lista_de(*velas))
    assert fragmento in str(error.value)


def test_serie_valida_pasa() -> None:
    validar_velas(generar_velas(100, Intervalo.M1))


def test_serie_vacia_y_de_una_vela_pasan() -> None:
    validar_velas(ListaDoble())
    validar_velas(lista_de(vela(0, 10, 12, 9, 11, 0)))


def test_velas_desordenadas_fallan_con_la_posicion() -> None:
    assert_invalida("posición 2: velas desordenadas",
                    vela(0, 10, 12, 9, 11, 1), vela(120_000, 10, 12, 9, 11, 1), vela(60_000, 10, 12, 9, 11, 1))


def test_velas_duplicadas_fallan() -> None:
    assert_invalida("posición 1: vela duplicada", vela(0, 10, 12, 9, 11, 1), vela(0, 10, 12, 9, 11, 1))


@pytest.mark.parametrize("mala", [
    vela(0, 0, 12, 9, 11, 1),
    vela(0, 10, 12, -9, 11, 1),
    vela(0, 10, math.nan, 9, 11, 1),
    vela(0, 10, math.inf, 9, 11, 1),
])
def test_precios_cero_negativos_o_no_finitos_fallan(mala: Vela) -> None:
    assert_invalida("positivos", mala)


def test_maximo_menor_que_minimo_falla() -> None:
    assert_invalida("máximo es menor que el mínimo", vela(0, 10, 9, 12, 11, 1))


def test_apertura_o_cierre_fuera_del_rango_fallan() -> None:
    assert_invalida("fuera del rango", vela(0, 13, 12, 9, 11, 1))
    assert_invalida("fuera del rango", vela(0, 10, 12, 9, 8, 1))


def test_volumen_negativo_falla() -> None:
    assert_invalida("volumen", vela(0, 10, 12, 9, 11, -1))


def test_tiempo_de_cierre_anterior_a_la_apertura_falla() -> None:
    assert_invalida("tiempo de cierre", Vela(1000, 10, 12, 9, 11, 1, 999))


def test_vela_nula_falla() -> None:
    lista: ListaDoble[Vela | None] = ListaDoble()
    lista.agregar_final(None)
    with pytest.raises(MercadoError):
        validar_velas(lista)  # type: ignore[arg-type]


# ---------- velas_cerradas ----------


def test_quita_solo_las_velas_que_no_han_cerrado() -> None:
    velas = generar_velas(5, Intervalo.D1)
    cierre_de_la_cuarta = velas.obtener(3).tiempo_cierre
    # "ahora" es justo el cierre de la cuarta: la cuarta y la quinta todavía no cerraron
    velas_cerradas(velas, cierre_de_la_cuarta)
    assert velas.tamanio() == 3
    # "ahora" antes de todo: ninguna vela cerró todavía
    velas_cerradas(velas, 0)
    assert velas.esta_vacia()


def test_si_todas_cerraron_no_cambia_nada() -> None:
    velas = generar_velas(5, Intervalo.D1)
    assert velas_cerradas(velas, velas.ultimo().tiempo_cierre + 1).tamanio() == 5
    assert velas_cerradas(ListaDoble(), 0).tamanio() == 0
