import pytest

from bitcoinai.estructuras import EstructuraVaciaError, IndiceFueraDeRangoError, Lista


def lista_de(*valores: int) -> Lista[int]:
    lista: Lista[int] = Lista()
    for v in valores:
        lista.agregar(v)
    return lista


def test_lista_nueva_esta_vacia() -> None:
    lista: Lista[int] = Lista()
    assert lista.esta_vacia()
    assert lista.tamanio() == 0
    assert len(lista) == 0
    assert tuple(lista) == ()


def test_primero_y_ultimo_en_lista_vacia_lanzan_excepcion() -> None:
    lista: Lista[int] = Lista()
    with pytest.raises(EstructuraVaciaError):
        lista.primero()
    with pytest.raises(EstructuraVaciaError):
        lista.ultimo()


def test_un_solo_elemento_es_primero_y_ultimo() -> None:
    lista = lista_de(7)
    assert lista.tamanio() == 1
    assert lista.primero() == 7
    assert lista.ultimo() == 7
    assert lista.obtener(0) == 7


def test_agregar_y_agregar_inicio_respetan_el_orden() -> None:
    lista: Lista[int] = Lista()
    lista.agregar(2)
    lista.agregar(3)
    lista.agregar_inicio(1)
    lista.agregar_inicio(0)
    assert tuple(lista) == (0, 1, 2, 3)
    assert lista.primero() == 0
    assert lista.ultimo() == 3


def test_agregar_inicio_en_lista_vacia_actualiza_la_cola() -> None:
    lista: Lista[int] = Lista()
    lista.agregar_inicio(5)
    lista.agregar(6)
    assert lista.primero() == 5
    assert lista.ultimo() == 6


def test_obtener_con_indice_invalido_lanza_excepcion() -> None:
    lista = lista_de(1, 2, 3)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.obtener(-1)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.obtener(3)
    with pytest.raises(IndiceFueraDeRangoError):
        Lista[int]().obtener(0)


def test_eliminar_con_indice_invalido_lanza_excepcion() -> None:
    lista = lista_de(1, 2)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.eliminar(-1)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.eliminar(2)
    assert lista.tamanio() == 2


def test_eliminar_cabeza_medio_y_cola_mantiene_extremos() -> None:
    lista = lista_de(1, 2, 3, 4, 5)
    assert lista.eliminar(0) == 1
    assert lista.eliminar(1) == 3
    assert lista.eliminar(2) == 5
    assert tuple(lista) == (2, 4)
    assert lista.primero() == 2
    assert lista.ultimo() == 4
    lista.agregar(6)
    assert tuple(lista) == (2, 4, 6)


def test_eliminar_el_unico_elemento_deja_la_lista_vacia_y_reutilizable() -> None:
    lista = lista_de(9)
    assert lista.eliminar(0) == 9
    assert lista.esta_vacia()
    with pytest.raises(EstructuraVaciaError):
        lista.ultimo()
    lista.agregar(10)
    assert lista.primero() == 10
    assert lista.ultimo() == 10


def test_insertar_ordenado_deja_la_lista_ordenada() -> None:
    lista: Lista[int] = Lista()
    for v in (5, 1, 4, 2, 3, 0, 6):
        lista.insertar_ordenado(v, clave=lambda x: x)
    assert tuple(lista) == (0, 1, 2, 3, 4, 5, 6)
    assert lista.primero() == 0
    assert lista.ultimo() == 6


def test_insertar_ordenado_es_estable_con_elementos_iguales() -> None:
    lista: Lista[str] = Lista()
    for palabra in ("bb", "a", "cc", "d"):
        lista.insertar_ordenado(palabra, clave=len)
    assert tuple(lista) == ("a", "d", "bb", "cc")


def test_buscar_devuelve_el_primer_indice_o_menos_uno() -> None:
    lista = lista_de(4, 8, 15, 16, 23, 42)
    assert lista.buscar(lambda v: v > 10) == 2
    assert lista.buscar(lambda v: v == 4) == 0
    assert lista.buscar(lambda v: v == 42) == 5
    assert lista.buscar(lambda v: v > 100) == -1
    assert Lista[int]().buscar(lambda v: True) == -1


def test_vaciar_deja_la_lista_vacia_y_reutilizable() -> None:
    lista = lista_de(1, 2, 3)
    lista.vaciar()
    assert lista.esta_vacia()
    assert lista.tamanio() == 0
    lista.agregar(4)
    assert tuple(lista) == (4,)


def test_iterador_termina_con_stop_iteration() -> None:
    iterador = iter(lista_de(1))
    assert next(iterador) == 1
    with pytest.raises(StopIteration):
        next(iterador)


def test_repr_muestra_los_elementos() -> None:
    assert repr(lista_de(1, 2, 3)) == "Lista(1, 2, 3)"
    assert repr(Lista[int]()) == "Lista()"
