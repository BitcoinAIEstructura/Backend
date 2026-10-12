import random

import pytest

from bitcoinai.estructuras import EstructuraVaciaError, Monticulo


def numeros(mayor_primero: bool = False) -> Monticulo[int]:
    return Monticulo(lambda x: x, mayor_primero=mayor_primero)


def vaciar(monticulo: Monticulo[int]) -> tuple[int, ...]:
    salida: tuple[int, ...] = ()
    while not monticulo.esta_vacia():
        salida += (monticulo.extraer(),)
    return salida


def test_monticulo_nuevo_esta_vacio() -> None:
    m = numeros()
    assert m.esta_vacia()
    assert len(m) == 0
    with pytest.raises(EstructuraVaciaError):
        m.ver_tope()
    with pytest.raises(EstructuraVaciaError):
        m.extraer()
    with pytest.raises(EstructuraVaciaError):
        m.reemplazar_tope(1)


def test_de_menor_a_mayor_por_defecto() -> None:
    m = numeros()
    for x in (5, 3, 8, 1, 9, 2):
        m.insertar(x)
    assert m.ver_tope() == 1
    assert vaciar(m) == (1, 2, 3, 5, 8, 9)


def test_mayor_primero() -> None:
    m = numeros(mayor_primero=True)
    for x in (5, 3, 8, 1):
        m.insertar(x)
    assert vaciar(m) == (8, 5, 3, 1)


def test_cada_padre_tiene_prioridad_sobre_sus_hijos() -> None:
    m = numeros()
    for x in (9, 4, 7, 1, 8, 2, 6):
        m.insertar(x)
    arreglo = tuple(m.en_orden_de_arreglo())
    for i in range(1, len(arreglo)):
        assert arreglo[(i - 1) // 2] <= arreglo[i]


def test_crece_al_doble_cuando_se_llena() -> None:
    m: Monticulo[int] = Monticulo(lambda x: x, capacidad=2)
    for x in range(5):
        m.insertar(x)
    assert m.capacidad() == 8
    assert vaciar(m) == (0, 1, 2, 3, 4)


def test_con_claves_iguales_sale_primero_el_que_llego_antes() -> None:
    m: Monticulo[tuple[str, int]] = Monticulo(lambda par: par[1])
    for par in (("a", 1), ("b", 0), ("c", 1), ("d", 1)):
        m.insertar(par)
    assert tuple(m.extraer()[0] for _ in range(4)) == ("b", "a", "c", "d")


def test_reemplazar_tope_para_quedarse_con_los_k_mayores() -> None:
    # Montículo de mínimos de tamaño 3: el tope es el peor de los 3 mejores.
    m = numeros()
    for x in (40, 10, 30, 50, 20, 60):
        if m.tamanio() < 3:
            m.insertar(x)
        elif x > m.ver_tope():
            assert m.reemplazar_tope(x) < x
    assert vaciar(m) == (40, 50, 60)


def test_cuenta_los_intercambios_de_la_ultima_operacion() -> None:
    m = numeros()
    for x in (5, 6, 7):
        m.insertar(x)
    assert m.intercambios_ultima_operacion() == 0
    m.insertar(1)  # sube de la casilla 3 a la 1 y luego a la 0
    assert m.intercambios_ultima_operacion() == 2


def test_coincide_con_ordenar_en_muchos_casos_al_azar() -> None:
    azar = random.Random(7)
    for _ in range(50):
        valores = tuple(azar.randint(-100, 100) for _ in range(azar.randint(0, 60)))
        m = numeros()
        for v in valores:
            m.insertar(v)
        assert vaciar(m) == tuple(sorted(valores))
