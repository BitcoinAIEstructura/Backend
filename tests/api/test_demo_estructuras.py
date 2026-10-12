import pytest

from bitcoinai.api.demo_estructuras import MAXIMO_OPERACIONES, DemoInvalidaError, Operacion, ejecutar


def ops(*pares: tuple[str, int | str | None]) -> tuple[Operacion, ...]:
    return tuple(Operacion(nombre, valor) for nombre, valor in pares)


def test_cola_fifo_paso_a_paso() -> None:
    pasos = ejecutar("cola", ops(("encolar", 1), ("encolar", 2), ("desencolar", None)))
    assert [p["estado"]["elementos"] for p in pasos] == [[1], [1, 2], [2]]
    assert pasos[2]["resultado"] == 1
    assert pasos[2]["complejidad"] == "O(1)"


def test_pila_lifo_y_sacar_de_vacia() -> None:
    pasos = ejecutar("pila", ops(("apilar", 1), ("apilar", 2), ("desapilar", None), ("desapilar", None),
                                 ("desapilar", None)))
    assert pasos[1]["estado"]["elementos"] == [2, 1]  # del tope al fondo
    assert pasos[2]["resultado"] == 2
    assert pasos[4]["descripcion"].startswith("Está vacía")


def test_monticulo_dice_cuanto_sube_y_cuando_crece() -> None:
    pasos = ejecutar("monticulo", ops(("insertar", 5), ("insertar", 7), ("insertar", 9), ("insertar", 8),
                                      ("insertar", 1), ("extraer", None)))
    assert pasos[4]["estado"]["arreglo"][0] == 1
    assert "sube 2 niveles" in pasos[4]["descripcion"]
    assert "creció a 8" in pasos[4]["descripcion"]
    assert pasos[5]["resultado"] == 1


def test_avl_cuenta_las_rotaciones() -> None:
    pasos = ejecutar("avl", ops(("insertar", 30), ("insertar", 20), ("insertar", 10), ("buscar", 20)))
    assert "Rotación simple a la derecha en 30" in pasos[2]["descripcion"]
    raiz = pasos[2]["estado"]["raiz"]
    assert (raiz["clave"], raiz["izquierdo"]["clave"], raiz["derecho"]["clave"]) == (20, 10, 30)
    assert pasos[3]["resultado"] is True


def test_tabla_hash_crece_al_pasar_el_factor() -> None:
    pasos = ejecutar("tabla-hash", ops(("poner", 1), ("poner", 2), ("poner", 3), ("poner", 4), ("buscar", 3)))
    assert pasos[2]["estado"]["capacidad"] == 4
    assert pasos[3]["estado"]["capacidad"] == 8 and "rehash" in pasos[3]["descripcion"]
    assert sum(len(c) for c in pasos[3]["estado"]["cubetas"]) == 4
    assert pasos[4]["resultado"] is True


def test_cola_circular_pisa_al_llenarse() -> None:
    pasos = ejecutar("cola-circular", ops(*(("agregar", i) for i in range(9))))
    ultimo = pasos[-1]
    assert ultimo["resultado"] == 0
    assert ultimo["estado"]["frente"] == 1
    assert ultimo["estado"]["casillas"][0] == 8


def test_trie_reutiliza_prefijos_y_sugiere() -> None:
    pasos = ejecutar("trie", ops(("insertar", "Orden"), ("insertar", "órdenes"), ("buscar", "ord")))
    assert "2 nodos nuevos; reutiliza 5" in pasos[1]["descripcion"]
    assert "Empiezan así: orden, ordenes" in pasos[2]["descripcion"]
    raiz = pasos[1]["estado"]["raiz"]
    assert raiz["hijos"][0]["letra"] == "o"
    assert pasos[1]["estado"]["nodos"] == 8


@pytest.mark.parametrize(("estructura", "operaciones", "fragmento"), [
    ("lista", (), "desconocida"),
    ("pila", ops(("encolar", 1)), "no válida"),
    ("avl", ops(("insertar", "x")), "entero"),
    ("avl", ops(("insertar", True)), "entero"),
    ("monticulo", ops(("insertar", 10**9)), "van de"),
    ("trie", ops(("insertar", 5)), "palabras"),
    ("trie", ops(("insertar", "dos palabras")), "Solo letras"),
    ("cola", ops(*(("encolar", 1),) * (MAXIMO_OPERACIONES + 1)), "Demasiadas"),
])
def test_peticiones_invalidas(estructura: str, operaciones: tuple[Operacion, ...], fragmento: str) -> None:
    with pytest.raises(DemoInvalidaError, match=fragmento):
        ejecutar(estructura, operaciones)
