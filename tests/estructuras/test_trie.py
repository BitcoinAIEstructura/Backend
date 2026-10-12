import random

import pytest

from bitcoinai.estructuras import EstructuraVaciaError, Trie


def trie_de(*palabras: str) -> Trie[int]:
    trie: Trie[int] = Trie()
    for i, p in enumerate(palabras):
        trie.insertar(p, i)
    return trie


def palabras(trie: Trie[int], prefijo: str = "", limite: int = 100) -> tuple[str, ...]:
    return tuple(p for p, _ in trie.con_prefijo(prefijo, limite))


def test_trie_vacio() -> None:
    trie: Trie[int] = Trie()
    assert trie.esta_vacio()
    assert trie.buscar("a") is None
    assert palabras(trie) == ()
    with pytest.raises(EstructuraVaciaError):
        trie.primera()
    with pytest.raises(ValueError, match="vacía"):
        trie.insertar("", 1)


def test_insertar_y_buscar_exacto() -> None:
    trie = trie_de("orden", "ordenes", "oro")
    assert trie.buscar("orden") == 0
    assert trie.contiene("oro")
    assert not trie.contiene("ord")  # es prefijo, no palabra
    assert trie.hay_prefijo("ord")
    assert not trie.insertar("oro", 9)
    assert trie.buscar("oro") == 9
    assert len(trie) == 3


def test_los_prefijos_comparten_nodos() -> None:
    trie = trie_de("cartera", "carta", "cola")
    # raíz + c-a-r-t + e-r-a + a + o-l-a = 1 + 4 + 3 + 1 + 3
    assert trie.cantidad_nodos() == 12


def test_con_prefijo_en_orden_alfabetico_y_con_limite() -> None:
    trie = trie_de("rsi", "riesgo", "rango", "ranking", "registro", "mercado")
    assert palabras(trie, "r") == ("rango", "ranking", "registro", "riesgo", "rsi")
    assert palabras(trie, "ra") == ("rango", "ranking")
    assert palabras(trie, "r", limite=2) == ("rango", "ranking")
    assert palabras(trie, "x") == ()
    assert trie.primera() == "mercado"


def test_la_palabra_igual_al_prefijo_sale_primero() -> None:
    trie = trie_de("bot", "bota", "botón")
    assert palabras(trie, "bot") == ("bot", "bota", "botón")


def test_eliminar_quita_los_nodos_que_sobran() -> None:
    trie = trie_de("orden", "ordenes")
    nodos = trie.cantidad_nodos()
    assert trie.eliminar("ordenes")
    assert trie.cantidad_nodos() == nodos - 2  # se van la "e" y la "s"
    assert trie.contiene("orden")
    assert not trie.eliminar("ordenes")
    assert not trie.eliminar("ord")  # prefijo, no palabra
    assert trie.eliminar("orden")
    assert trie.cantidad_nodos() == 1 and trie.esta_vacio()


def test_coincide_con_filtrar_un_conjunto_al_azar() -> None:
    azar = random.Random(5)
    trie: Trie[int] = Trie()
    referencia: set[str] = set()
    for paso in range(1500):
        palabra = "".join(azar.choice("abc") for _ in range(azar.randint(1, 5)))
        if azar.random() < 0.7:
            trie.insertar(palabra, paso)
            referencia.add(palabra)
        else:
            assert trie.eliminar(palabra) == (palabra in referencia)
            referencia.discard(palabra)
    for prefijo in ("", "a", "ab", "cab", "bbb"):
        esperado = tuple(sorted(p for p in referencia if p.startswith(prefijo)))
        assert palabras(trie, prefijo, limite=10_000) == esperado


def test_recorrer_los_nodos_para_dibujar() -> None:
    trie = trie_de("sol", "sal")
    (s,) = tuple(trie.raiz().hijos())
    assert s.letra == "s"
    assert tuple(h.letra for h in s.hijos()) == ("a", "o")
    (ele,) = tuple(tuple(s.hijos())[0].hijos())
    assert ele.tiene_valor and tuple(ele.hijos()) == ()
