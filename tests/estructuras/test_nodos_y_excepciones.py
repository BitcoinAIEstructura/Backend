import pytest

from bitcoinai.estructuras import EstructuraVaciaError, IndiceFueraDeRangoError, NodoDoble, NodoSimple


def test_nodo_simple_nuevo_no_tiene_siguiente() -> None:
    nodo = NodoSimple("a")
    assert nodo.valor == "a"
    assert nodo.siguiente is None


def test_nodo_simple_se_puede_enlazar() -> None:
    segundo = NodoSimple("b")
    primero = NodoSimple("a", segundo)
    assert primero.siguiente is segundo


def test_nodo_simple_acepta_valor_nulo() -> None:
    assert NodoSimple(None).valor is None


def test_nodo_doble_nuevo_no_tiene_vecinos() -> None:
    nodo = NodoDoble(1)
    assert nodo.valor == 1
    assert nodo.anterior is None
    assert nodo.siguiente is None


def test_los_enlaces_no_se_pueden_cambiar_desde_fuera() -> None:
    nodo = NodoSimple(1)
    with pytest.raises(AttributeError):
        nodo.siguiente = NodoSimple(2)  # type: ignore[misc]
    with pytest.raises(AttributeError):
        nodo.otro_atributo = 3  # type: ignore[attr-defined]  # __slots__ no deja agregar atributos


def test_estructura_vacia_es_una_excepcion_con_mensaje() -> None:
    error = EstructuraVaciaError("La cola está vacía")
    assert isinstance(error, Exception)
    assert str(error) == "La cola está vacía"


def test_indice_fuera_de_rango_indica_indice_y_tamanio() -> None:
    error = IndiceFueraDeRangoError(5, 3)
    assert isinstance(error, IndexError)
    assert str(error) == "Índice 5 fuera de rango para tamaño 3"
    assert error.indice == 5
    assert error.tamanio == 3
