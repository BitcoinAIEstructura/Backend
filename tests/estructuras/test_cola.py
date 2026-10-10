import pytest

from bitcoinai.estructuras import Cola, EstructuraVaciaError


def test_cola_nueva_esta_vacia() -> None:
    cola: Cola[str] = Cola()
    assert cola.esta_vacia()
    assert cola.tamanio() == 0
    assert len(cola) == 0


def test_desencolar_y_ver_frente_en_cola_vacia_lanzan_excepcion() -> None:
    cola: Cola[str] = Cola()
    with pytest.raises(EstructuraVaciaError):
        cola.desencolar()
    with pytest.raises(EstructuraVaciaError):
        cola.ver_frente()


def test_un_solo_elemento() -> None:
    cola: Cola[str] = Cola()
    cola.encolar("a")
    assert not cola.esta_vacia()
    assert cola.tamanio() == 1
    assert cola.ver_frente() == "a"
    assert cola.desencolar() == "a"
    assert cola.esta_vacia()


def test_respeta_el_orden_fifo() -> None:
    cola: Cola[int] = Cola()
    for i in range(1, 6):
        cola.encolar(i)
    for i in range(1, 6):
        assert cola.desencolar() == i
    assert cola.esta_vacia()


def test_ver_frente_no_quita_el_elemento() -> None:
    cola: Cola[int] = Cola()
    cola.encolar(1)
    cola.encolar(2)
    assert cola.ver_frente() == 1
    assert cola.ver_frente() == 1
    assert cola.tamanio() == 2


def test_encolar_y_desencolar_intercalados_mantienen_el_orden() -> None:
    cola: Cola[int] = Cola()
    cola.encolar(1)
    cola.encolar(2)
    assert cola.desencolar() == 1
    cola.encolar(3)
    assert cola.desencolar() == 2
    cola.encolar(4)
    assert cola.desencolar() == 3
    assert cola.desencolar() == 4
    assert cola.esta_vacia()


def test_se_puede_reutilizar_despues_de_quedar_vacia_al_desencolar() -> None:
    cola: Cola[int] = Cola()
    cola.encolar(1)
    cola.desencolar()
    with pytest.raises(EstructuraVaciaError):
        cola.ver_frente()
    cola.encolar(2)
    cola.encolar(3)
    assert cola.desencolar() == 2
    assert cola.desencolar() == 3


def test_vaciar_quita_todo_y_permite_reutilizar() -> None:
    cola: Cola[int] = Cola()
    cola.encolar(1)
    cola.encolar(2)
    cola.vaciar()
    assert cola.esta_vacia()
    with pytest.raises(EstructuraVaciaError):
        cola.desencolar()
    cola.encolar(3)
    assert cola.ver_frente() == 3
    assert cola.tamanio() == 1


def test_tamanio_correcto_con_muchos_elementos() -> None:
    cola: Cola[int] = Cola()
    for i in range(10_000):
        cola.encolar(i)
    assert cola.tamanio() == 10_000
    for _ in range(9_999):
        cola.desencolar()
    assert cola.tamanio() == 1
    assert cola.ver_frente() == 9_999


def test_no_es_iterable_y_tiene_repr() -> None:
    cola: Cola[int] = Cola()
    cola.encolar(1)
    assert not hasattr(cola, "__iter__")
    assert repr(cola) == "Cola(tamanio=1)"
