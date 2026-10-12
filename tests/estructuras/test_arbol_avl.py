import math
import random
from typing import Any

import pytest

from bitcoinai.estructuras import ArbolAVL, EstructuraVaciaError, NodoAVL


def arbol_de(*claves: int) -> ArbolAVL[int, str]:
    arbol: ArbolAVL[int, str] = ArbolAVL()
    for c in claves:
        arbol.insertar(c, f"v{c}")
    return arbol


def revisar_invariantes(nodo: NodoAVL[int, Any] | None) -> int:
    """Comprueba orden, balance y alturas guardadas; devuelve la altura."""
    if nodo is None:
        return 0
    izquierda = revisar_invariantes(nodo.izquierdo)
    derecha = revisar_invariantes(nodo.derecho)
    if nodo.izquierdo is not None:
        assert nodo.izquierdo.clave < nodo.clave
    if nodo.derecho is not None:
        assert nodo.clave < nodo.derecho.clave
    assert abs(izquierda - derecha) <= 1
    assert nodo.altura == 1 + max(izquierda, derecha)
    return nodo.altura


def rotaciones(arbol: ArbolAVL[int, str]) -> tuple[str, ...]:
    return tuple(arbol.rotaciones_ultima_operacion())


def test_arbol_vacio() -> None:
    arbol: ArbolAVL[int, str] = ArbolAVL()
    assert arbol.esta_vacio()
    assert arbol.altura() == 0
    assert arbol.buscar(1) is None
    assert arbol.techo(1) is None
    with pytest.raises(EstructuraVaciaError):
        arbol.minimo()
    with pytest.raises(EstructuraVaciaError):
        arbol.maximo()


def test_insertar_buscar_y_cambiar_valor() -> None:
    arbol = arbol_de(5, 2, 8)
    assert arbol.buscar(2) == "v2"
    assert arbol.contiene(8)
    assert not arbol.contiene(3)
    assert arbol.insertar(2, "otro") is False
    assert arbol.buscar(2) == "otro"
    assert arbol.tamanio() == 3


def test_los_cuatro_casos_de_rotacion() -> None:
    arbol = arbol_de(30, 20)
    arbol.insertar(10, "")
    assert rotaciones(arbol) == ("Rotación simple a la derecha en 30",)
    arbol = arbol_de(10, 20)
    arbol.insertar(30, "")
    assert rotaciones(arbol) == ("Rotación simple a la izquierda en 10",)
    arbol = arbol_de(30, 10)
    arbol.insertar(20, "")
    assert rotaciones(arbol) == ("Rotación doble izquierda-derecha en 30",)
    arbol = arbol_de(10, 30)
    arbol.insertar(20, "")
    assert rotaciones(arbol) == ("Rotación doble derecha-izquierda en 10",)
    raiz = arbol.raiz()
    assert raiz is not None and raiz.clave == 20


def test_claves_ordenadas_no_lo_vuelven_una_lista() -> None:
    # Como las velas: llegan en orden. Sin balanceo, la altura sería 1000.
    arbol = arbol_de(*range(1000))
    assert arbol.altura() <= 1.45 * math.log2(1001)
    assert revisar_invariantes(arbol.raiz()) == arbol.altura()


def test_eliminar_hoja_un_hijo_y_dos_hijos() -> None:
    arbol = arbol_de(50, 30, 70, 20, 40, 60, 80, 35)
    assert arbol.eliminar(20)  # hoja
    assert arbol.eliminar(40)  # un hijo (35)
    assert arbol.eliminar(50)  # dos hijos: lo reemplaza 60
    assert not arbol.eliminar(99)
    assert tuple(c for c, _ in arbol.en_orden()) == (30, 35, 60, 70, 80)
    assert arbol.buscar(35) == "v35"
    revisar_invariantes(arbol.raiz())


def test_techo_y_piso() -> None:
    arbol = arbol_de(10, 20, 30, 40)
    assert arbol.techo(20) == (20, "v20")
    assert arbol.techo(21) == (30, "v30")
    assert arbol.techo(41) is None
    assert arbol.piso(29) == (20, "v20")
    assert arbol.piso(9) is None
    assert arbol.minimo() == (10, "v10")
    assert arbol.maximo() == (40, "v40")


def test_rango_incluye_los_extremos() -> None:
    arbol = arbol_de(*range(0, 100, 10))
    assert tuple(c for c, _ in arbol.rango(25, 60)) == (30, 40, 50, 60)
    assert tuple(arbol.rango(91, 95)) == ()


def test_coincide_con_un_diccionario_en_operaciones_al_azar() -> None:
    azar = random.Random(11)
    arbol: ArbolAVL[int, int] = ArbolAVL()
    referencia: dict[int, int] = {}
    for paso in range(2000):
        clave = azar.randint(0, 300)
        if azar.random() < 0.6:
            assert arbol.insertar(clave, paso) == (clave not in referencia)
            referencia[clave] = paso
        else:
            assert arbol.eliminar(clave) == (referencia.pop(clave, None) is not None)
    assert tuple(arbol.en_orden()) == tuple(sorted(referencia.items()))
    assert arbol.tamanio() == len(referencia)
    revisar_invariantes(arbol.raiz())
    for clave in range(-5, 310):
        mayores = [c for c in referencia if c >= clave]
        assert arbol.techo(clave) == ((min(mayores), referencia[min(mayores)]) if mayores else None)
