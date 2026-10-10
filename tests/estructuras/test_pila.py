import pytest

from bitcoinai.estructuras import EstructuraVaciaError, Pila


def test_pila_nueva_esta_vacia() -> None:
    pila: Pila[str] = Pila()
    assert pila.esta_vacia()
    assert pila.tamanio() == 0
    assert len(pila) == 0


def test_desapilar_y_ver_tope_en_pila_vacia_lanzan_excepcion() -> None:
    pila: Pila[str] = Pila()
    with pytest.raises(EstructuraVaciaError):
        pila.desapilar()
    with pytest.raises(EstructuraVaciaError):
        pila.ver_tope()


def test_un_solo_elemento() -> None:
    pila: Pila[str] = Pila()
    pila.apilar("a")
    assert not pila.esta_vacia()
    assert pila.tamanio() == 1
    assert pila.ver_tope() == "a"
    assert pila.desapilar() == "a"
    assert pila.esta_vacia()


def test_respeta_el_orden_lifo() -> None:
    pila: Pila[int] = Pila()
    for i in range(1, 6):
        pila.apilar(i)
    for i in range(5, 0, -1):
        assert pila.desapilar() == i
    assert pila.esta_vacia()


def test_ver_tope_no_quita_el_elemento() -> None:
    pila: Pila[int] = Pila()
    pila.apilar(1)
    pila.apilar(2)
    assert pila.ver_tope() == 2
    assert pila.ver_tope() == 2
    assert pila.tamanio() == 2


def test_apilar_y_desapilar_intercalados() -> None:
    pila: Pila[int] = Pila()
    pila.apilar(1)
    pila.apilar(2)
    assert pila.desapilar() == 2
    pila.apilar(3)
    assert pila.desapilar() == 3
    assert pila.desapilar() == 1
    assert pila.esta_vacia()


def test_se_puede_reutilizar_despues_de_quedar_vacia() -> None:
    pila: Pila[int] = Pila()
    pila.apilar(1)
    pila.desapilar()
    with pytest.raises(EstructuraVaciaError):
        pila.ver_tope()
    pila.apilar(2)
    assert pila.ver_tope() == 2
    assert pila.tamanio() == 1


def test_vaciar_quita_todo() -> None:
    pila: Pila[int] = Pila()
    pila.apilar(1)
    pila.apilar(2)
    pila.vaciar()
    assert pila.esta_vacia()
    assert pila.tamanio() == 0
    with pytest.raises(EstructuraVaciaError):
        pila.desapilar()


def test_tamanio_correcto_con_muchos_elementos() -> None:
    pila: Pila[int] = Pila()
    for i in range(10_000):
        pila.apilar(i)
    assert pila.tamanio() == 10_000
    assert pila.ver_tope() == 9_999
    for _ in range(9_999):
        pila.desapilar()
    assert pila.ver_tope() == 0


def test_no_es_iterable_y_tiene_repr() -> None:
    pila: Pila[int] = Pila()
    pila.apilar(1)
    assert not hasattr(pila, "__iter__")
    assert repr(pila) == "Pila(tamanio=1)"
