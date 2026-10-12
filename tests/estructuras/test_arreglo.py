import pytest

from bitcoinai.estructuras import Arreglo, IndiceFueraDeRangoError


def test_arreglo_nuevo_tiene_casillas_vacias() -> None:
    arreglo: Arreglo[str] = Arreglo(3)
    assert arreglo.capacidad() == 3
    assert len(arreglo) == 3
    assert tuple(arreglo) == (None, None, None)


def test_poner_y_obtener() -> None:
    arreglo: Arreglo[str] = Arreglo(2)
    arreglo.poner(0, "a")
    arreglo.poner(1, "b")
    assert arreglo.obtener(0) == "a"
    assert arreglo.obtener(1) == "b"
    arreglo.poner(0, None)
    assert arreglo.obtener(0) is None


def test_indices_fuera_de_rango() -> None:
    arreglo: Arreglo[int] = Arreglo(2)
    with pytest.raises(IndiceFueraDeRangoError):
        arreglo.obtener(2)
    with pytest.raises(IndiceFueraDeRangoError):
        arreglo.poner(-1, 5)
    with pytest.raises(IndiceFueraDeRangoError):
        arreglo.intercambiar(0, 9)


def test_intercambiar() -> None:
    arreglo: Arreglo[int] = Arreglo(2)
    arreglo.poner(0, 1)
    arreglo.poner(1, 2)
    arreglo.intercambiar(0, 1)
    assert tuple(arreglo) == (2, 1)


def test_copiar_en_uno_mas_grande_para_crecer() -> None:
    chico: Arreglo[int] = Arreglo(2)
    chico.poner(0, 7)
    chico.poner(1, 8)
    grande: Arreglo[int] = Arreglo(4)
    chico.copiar_en(grande, 2)
    assert tuple(grande) == (7, 8, None, None)


def test_capacidad_cero_y_negativa() -> None:
    assert tuple(Arreglo[int](0)) == ()
    with pytest.raises(ValueError, match="negativa"):
        Arreglo[int](-1)


def test_guarda_objetos_cualquiera_sin_copiarlos() -> None:
    dato = {"precio": 1}
    arreglo: Arreglo[dict[str, int]] = Arreglo(1)
    arreglo.poner(0, dato)
    assert arreglo.obtener(0) is dato
