import pytest

from bitcoinai.estructuras import EstructuraVaciaError, IndiceFueraDeRangoError, ListaDoble, NodoDoble


def lista_de(*valores: int) -> ListaDoble[int]:
    lista: ListaDoble[int] = ListaDoble()
    for v in valores:
        lista.agregar_final(v)
    return lista


def adelante[T](lista: ListaDoble[T]) -> tuple[T, ...]:
    resultado = tuple(lista.iterador_adelante())
    assert len(resultado) == lista.tamanio(), "el iterador debe recorrer exactamente tamanio() elementos"
    return resultado


def atras[T](lista: ListaDoble[T]) -> tuple[T, ...]:
    resultado = tuple(lista.iterador_atras())
    assert len(resultado) == lista.tamanio(), "el iterador debe recorrer exactamente tamanio() elementos"
    return resultado


def test_lista_nueva_esta_vacia() -> None:
    lista: ListaDoble[int] = ListaDoble()
    assert lista.esta_vacia()
    assert lista.tamanio() == 0
    assert adelante(lista) == ()
    assert atras(lista) == ()


def test_operaciones_sobre_lista_vacia_lanzan_excepcion() -> None:
    lista: ListaDoble[int] = ListaDoble()
    for operacion in (lista.eliminar_primero, lista.eliminar_ultimo, lista.primero, lista.ultimo):
        with pytest.raises(EstructuraVaciaError):
            operacion()
    with pytest.raises(StopIteration):
        next(lista.iterador_atras())


def test_un_solo_elemento_se_quita_por_cualquier_extremo() -> None:
    lista = lista_de(1)
    assert lista.primero() == 1
    assert lista.ultimo() == 1
    assert lista.eliminar_ultimo() == 1
    assert lista.esta_vacia()
    with pytest.raises(EstructuraVaciaError):
        lista.primero()

    lista.agregar_inicio(2)
    assert lista.eliminar_primero() == 2
    assert lista.esta_vacia()
    with pytest.raises(EstructuraVaciaError):
        lista.ultimo()


def test_agregar_en_ambos_extremos_respeta_el_orden() -> None:
    lista: ListaDoble[int] = ListaDoble()
    lista.agregar_final(2)
    lista.agregar_inicio(1)
    lista.agregar_final(3)
    lista.agregar_inicio(0)
    assert adelante(lista) == (0, 1, 2, 3)
    assert lista.primero() == 0
    assert lista.ultimo() == 3


def test_insertar_al_inicio_en_medio_y_al_final() -> None:
    lista = lista_de(1, 3)
    lista.insertar(1, 2)
    lista.insertar(0, 0)
    lista.insertar(4, 4)
    assert adelante(lista) == (0, 1, 2, 3, 4)
    assert atras(lista) == (4, 3, 2, 1, 0)


def test_insertar_con_indice_invalido_lanza_excepcion() -> None:
    lista = lista_de(1, 2)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.insertar(-1, 9)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.insertar(3, 9)
    assert lista.tamanio() == 2


def test_obtener_devuelve_cada_posicion_desde_ambos_extremos() -> None:
    par = lista_de(*range(10))
    for i in range(par.tamanio()):
        assert par.obtener(i) == i
    impar = lista_de(*range(5))
    for i in range(impar.tamanio()):
        assert impar.obtener(i) == i


def test_obtener_y_eliminar_con_indice_invalido_lanzan_excepcion() -> None:
    lista = lista_de(1, 2, 3)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.obtener(-1)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.obtener(3)
    with pytest.raises(IndiceFueraDeRangoError):
        lista.eliminar(3)
    with pytest.raises(IndiceFueraDeRangoError):
        ListaDoble[int]().obtener(0)


def test_eliminar_por_indice_en_extremos_y_en_medio() -> None:
    lista = lista_de(0, 1, 2, 3, 4, 5)
    assert lista.eliminar(3) == 3
    assert lista.eliminar(0) == 0
    assert lista.eliminar(lista.tamanio() - 1) == 5
    assert adelante(lista) == (1, 2, 4)
    assert lista.primero() == 1
    assert lista.ultimo() == 4


def test_conservar_ultimos_descarta_los_mas_antiguos() -> None:
    lista = lista_de(*range(1, 11))
    lista.conservar_ultimos(3)
    assert adelante(lista) == (8, 9, 10)

    lista.conservar_ultimos(5)
    assert lista.tamanio() == 3

    lista.agregar_final(11)
    lista.conservar_ultimos(3)
    assert adelante(lista) == (9, 10, 11)
    assert atras(lista) == (11, 10, 9)

    lista.conservar_ultimos(0)
    assert lista.esta_vacia()
    with pytest.raises(ValueError):
        lista.conservar_ultimos(-1)


def test_recorrido_atras_es_el_inverso_del_recorrido_adelante_tras_varias_operaciones() -> None:
    lista: ListaDoble[int] = ListaDoble()
    for i in range(20):
        if i % 2 == 0:
            lista.agregar_final(i)
        else:
            lista.agregar_inicio(i)
    lista.insertar(5, 100)
    lista.insertar(15, 200)
    lista.eliminar_primero()
    lista.eliminar_ultimo()
    lista.eliminar(7)
    lista.eliminar(12)
    lista.conservar_ultimos(14)
    lista.agregar_final(300)
    lista.insertar(0, 400)

    assert atras(lista) == tuple(reversed(adelante(lista)))
    assert lista.tamanio() == 16
    assert lista.primero() == 400
    assert lista.ultimo() == 300


def test_vaciar_deja_la_lista_vacia_y_reutilizable() -> None:
    lista = lista_de(1, 2, 3)
    lista.vaciar()
    assert lista.esta_vacia()
    assert atras(lista) == ()
    lista.agregar_inicio(4)
    lista.agregar_final(5)
    assert adelante(lista) == (4, 5)
    assert atras(lista) == (5, 4)


def test_for_recorre_hacia_adelante() -> None:
    assert "".join(str(v) for v in lista_de(3, 1, 2)) == "312"
    assert len(lista_de(3, 1, 2)) == 3
    assert repr(lista_de(1, 2)) == "ListaDoble(1, 2)"


# ---------- eliminar por nodo en O(1) ----------


def test_eliminar_nodo_quita_del_medio_y_de_los_extremos_sin_recorrer() -> None:
    lista: ListaDoble[str] = ListaDoble()
    a = lista.agregar_final_nodo("a")
    b = lista.agregar_final_nodo("b")
    c = lista.agregar_final_nodo("c")
    d = lista.agregar_final_nodo("d")
    assert b.valor == "b"

    assert lista.eliminar_nodo(b)  # del medio
    assert adelante(lista) == ("a", "c", "d")
    assert lista.eliminar_nodo(a)  # la cabeza
    assert lista.eliminar_nodo(d)  # la cola
    assert adelante(lista) == ("c",)
    assert atras(lista) == ("c",)
    assert lista.primero() == "c"
    assert lista.ultimo() == "c"
    assert lista.eliminar_nodo(c)
    assert lista.esta_vacia()


def test_eliminar_nodo_dos_veces_o_de_otra_lista_es_seguro() -> None:
    lista = lista_de(1, 2)
    otra: ListaDoble[int] = ListaDoble()
    nodo = lista.agregar_final_nodo(3)
    ajeno = otra.agregar_final_nodo(9)

    assert lista.eliminar_nodo(nodo)
    assert not lista.eliminar_nodo(nodo)  # ya se había quitado
    assert not lista.eliminar_nodo(ajeno)  # es de otra lista
    assert not lista.eliminar_nodo(None)
    assert not lista.eliminar_nodo(NodoDoble(5))
    assert adelante(lista) == (1, 2)
    assert otra.tamanio() == 1


def test_tras_vaciar_los_nodos_viejos_quedan_invalidos() -> None:
    lista: ListaDoble[int] = ListaDoble()
    viejo = lista.agregar_final_nodo(1)
    lista.vaciar()
    lista.agregar_final(2)
    assert not lista.eliminar_nodo(viejo)
    assert lista.tamanio() == 1
    # Un nodo quitado con eliminar_ultimo también deja de pertenecer.
    quitado = lista.agregar_final_nodo(3)
    lista.eliminar_ultimo()
    assert not lista.eliminar_nodo(quitado)
    assert adelante(lista) == (2,)
