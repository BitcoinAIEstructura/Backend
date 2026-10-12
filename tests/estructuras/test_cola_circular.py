import pytest

from bitcoinai.estructuras import ColaCircular, ColaLlenaError, EstructuraVaciaError, IndiceFueraDeRangoError


def test_cola_nueva() -> None:
    cola: ColaCircular[int] = ColaCircular(3)
    assert cola.esta_vacia()
    assert not cola.esta_llena()
    assert cola.capacidad() == 3
    with pytest.raises(EstructuraVaciaError):
        cola.desencolar()
    with pytest.raises(EstructuraVaciaError):
        cola.ver_frente()
    with pytest.raises(EstructuraVaciaError):
        cola.ver_final()


def test_capacidad_invalida() -> None:
    with pytest.raises(ValueError, match="positiva"):
        ColaCircular[int](0)


def test_fifo_y_llena() -> None:
    cola: ColaCircular[int] = ColaCircular(3)
    for i in (1, 2, 3):
        cola.encolar(i)
    assert cola.esta_llena()
    with pytest.raises(ColaLlenaError):
        cola.encolar(4)
    assert cola.desencolar() == 1
    assert cola.ver_frente() == 2
    assert cola.ver_final() == 3


def test_da_la_vuelta_sin_mover_elementos() -> None:
    cola: ColaCircular[str] = ColaCircular(3)
    for c in "abc":
        cola.encolar(c)
    cola.desencolar()
    cola.desencolar()
    cola.encolar("d")  # cae en la casilla 0
    cola.encolar("e")  # casilla 1
    assert cola.indice_frente() == 2
    assert tuple(cola.casillas()) == ("d", "e", "c")
    assert tuple(cola) == ("c", "d", "e")


def test_agregar_pisa_al_mas_viejo() -> None:
    cola: ColaCircular[int] = ColaCircular(3)
    for i in range(1, 4):
        assert cola.agregar(i) is None
    assert cola.agregar(4) == 1
    assert cola.agregar(5) == 2
    assert tuple(cola) == (3, 4, 5)
    assert cola.tamanio() == 3


def test_obtener_por_posicion() -> None:
    cola: ColaCircular[int] = ColaCircular(2)
    for i in range(10):
        cola.agregar(i)
    assert cola.obtener(0) == 8
    assert cola.obtener(1) == 9
    with pytest.raises(IndiceFueraDeRangoError):
        cola.obtener(2)


def test_ultimos_n_precios() -> None:
    precios: ColaCircular[float] = ColaCircular(120)
    for i in range(500):
        precios.agregar(80_000 + i)
    assert precios.tamanio() == 120
    assert precios.ver_frente() == 80_380
    assert precios.ver_final() == 80_499
