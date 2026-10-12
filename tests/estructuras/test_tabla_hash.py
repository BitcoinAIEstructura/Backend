import random

from bitcoinai.estructuras import TablaHash


class ClaveQueChoca:
    """Todas tienen el mismo hash: obliga a encadenar en una sola cubeta."""

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre

    def __hash__(self) -> int:
        return 42

    def __eq__(self, otra: object) -> bool:
        return isinstance(otra, ClaveQueChoca) and otra.nombre == self.nombre


def test_tabla_nueva() -> None:
    tabla: TablaHash[str, int] = TablaHash()
    assert tabla.esta_vacia()
    assert tabla.capacidad() == 8
    assert tabla.obtener("x") is None
    assert not tabla.eliminar("x")


def test_poner_obtener_cambiar_y_eliminar() -> None:
    tabla: TablaHash[str, int] = TablaHash()
    assert tabla.poner("a", 1)
    assert tabla.poner("b", 2)
    assert not tabla.poner("a", 10)
    assert tabla.obtener("a") == 10
    assert tabla.contiene("b")
    assert tabla.eliminar("a")
    assert not tabla.contiene("a")
    assert len(tabla) == 1


def test_la_capacidad_se_sube_a_potencia_de_dos() -> None:
    assert TablaHash[int, int](10).capacidad() == 16
    assert TablaHash[int, int](1).capacidad() == 1


def test_crece_al_doble_sin_pasar_el_factor_de_carga() -> None:
    tabla: TablaHash[int, int] = TablaHash()
    for i in range(100):
        tabla.poner(i, i * i)
        assert tabla.factor_de_carga() <= 0.75
    assert tabla.capacidad() == 256
    assert all(tabla.obtener(i) == i * i for i in range(100))


def test_colisiones_se_encadenan_y_se_borran_bien() -> None:
    tabla: TablaHash[ClaveQueChoca, int] = TablaHash()
    claves = [ClaveQueChoca(n) for n in "abcd"]
    for i, clave in enumerate(claves):
        tabla.poner(clave, i)
    longitudes = tuple(tabla.longitudes_de_cubetas())
    assert max(longitudes) == 4 and sum(longitudes) == 4
    assert tabla.eliminar(ClaveQueChoca("c"))  # del medio de la cadena
    assert tabla.eliminar(ClaveQueChoca("d"))  # la cabeza (se inserta al frente)
    assert tabla.obtener(ClaveQueChoca("a")) == 0
    assert tabla.obtener(ClaveQueChoca("b")) == 1
    assert tabla.obtener(ClaveQueChoca("c")) is None


def test_ids_seguidos_quedan_bien_repartidos() -> None:
    tabla: TablaHash[int, None] = TablaHash()
    for usuario_id in range(1, 97):
        tabla.poner(usuario_id, None)
    assert max(tabla.longitudes_de_cubetas()) <= 2


def test_elementos_y_valores() -> None:
    tabla: TablaHash[str, int] = TablaHash()
    for i, c in enumerate("xyz"):
        tabla.poner(c, i)
    assert sorted(tabla.elementos()) == [("x", 0), ("y", 1), ("z", 2)]
    assert sorted(tabla.valores()) == [0, 1, 2]


def test_coincide_con_un_diccionario_en_operaciones_al_azar() -> None:
    azar = random.Random(3)
    tabla: TablaHash[int, int] = TablaHash()
    referencia: dict[int, int] = {}
    for paso in range(3000):
        clave = azar.randint(0, 500)
        if azar.random() < 0.65:
            assert tabla.poner(clave, paso) == (clave not in referencia)
            referencia[clave] = paso
        else:
            assert tabla.eliminar(clave) == (referencia.pop(clave, None) is not None)
    assert sorted(tabla.elementos()) == sorted(referencia.items())
    assert tabla.tamanio() == len(referencia)


def test_claves_por_cubeta_sigue_la_cadena() -> None:
    tabla: TablaHash[ClaveQueChoca, int] = TablaHash(2)
    tabla.poner(ClaveQueChoca("a"), 1)
    tabla.poner(ClaveQueChoca("b"), 2)  # entra al frente de la cadena
    cubetas = tuple(tuple(c.nombre for c in cubeta) for cubeta in tabla.claves_por_cubeta())
    # Con 2 claves en 2 cubetas el factor sería 1 > 0,75: creció a 4. Las dos chocan: cadena b → a.
    assert sorted(cubetas) == [(), (), (), ("b", "a")]
