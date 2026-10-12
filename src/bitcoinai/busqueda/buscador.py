"""Buscador por prefijos: un Trie de palabras normalizadas y una TablaHash para no repetir."""

import unicodedata
from collections.abc import Iterable

from bitcoinai.busqueda.catalogo import CATALOGO, Entrada
from bitcoinai.estructuras import Lista, TablaHash, Trie

LIMITE_POR_DEFECTO = 8
LARGO_MAXIMO_CONSULTA = 60


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes: "Órdenes" → "ordenes". Así no importa cómo se escriba."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def palabras(texto: str) -> Iterable[str]:
    """Las palabras de un texto normalizado (letras y números; lo demás separa)."""
    actual = ""
    for c in normalizar(texto):
        if c.isalnum():
            actual += c
        elif actual:
            yield actual
            actual = ""
    if actual:
        yield actual


class Buscador:
    """Encuentra entradas del catálogo mientras se escribe.

    - Cada palabra del título, la descripción y las claves va al ``Trie`` con la
      lista de entradas donde aparece.
    - Al buscar, cada palabra de la consulta se toma como prefijo ("ord" encuentra
      "ordenes" y "orden"). Una entrada sale si coincide con todas las palabras.
    - Una ``TablaHash`` por palabra junta las entradas sin repetirlas.
    - Primero salen las que coinciden en el título; después, en el orden del catálogo.
    """

    def __init__(self, catalogo: Iterable[Entrada] = CATALOGO) -> None:
        self._trie: Trie[Lista[int]] = Trie()
        self._entradas: Lista[Entrada] = Lista()
        for indice, entrada in enumerate(catalogo):
            self._entradas.agregar(entrada)
            vistas: TablaHash[str, None] = TablaHash()
            for palabra in palabras(f"{entrada.titulo} {entrada.descripcion} {entrada.claves}"):
                if vistas.poner(palabra, None):
                    donde = self._trie.buscar(palabra)
                    if donde is None:
                        donde = Lista()
                        self._trie.insertar(palabra, donde)
                    donde.agregar(indice)

    def _con_prefijo(self, prefijo: str) -> TablaHash[int, None]:
        """Índices de las entradas con alguna palabra que empiece así. O(m·a + nodos visitados)."""
        encontradas: TablaHash[int, None] = TablaHash()
        for _, indices in self._trie.con_prefijo(prefijo, limite=1000):
            for indice in indices:
                encontradas.poner(indice, None)
        return encontradas

    def buscar(self, consulta: str, limite: int = LIMITE_POR_DEFECTO) -> Lista[Entrada]:
        """Hasta ``limite`` entradas que coinciden con todas las palabras de la consulta."""
        resultado: Lista[Entrada] = Lista()
        terminos: Lista[str] = Lista()
        for palabra in palabras(consulta[:LARGO_MAXIMO_CONSULTA]):
            terminos.agregar(palabra)
        if terminos.esta_vacia() or limite <= 0:
            return resultado
        comunes: TablaHash[int, None] | None = None
        for termino in terminos:
            encontradas = self._con_prefijo(termino)
            if comunes is None:
                comunes = encontradas
            else:
                interseccion: TablaHash[int, None] = TablaHash()
                for indice, _ in comunes.elementos():
                    if encontradas.contiene(indice):
                        interseccion.poner(indice, None)
                comunes = interseccion
        assert comunes is not None
        en_titulo: Lista[Entrada] = Lista()
        en_otro_lado: Lista[Entrada] = Lista()
        for indice, entrada in enumerate(self._entradas):
            if comunes.contiene(indice):
                titulo = normalizar(entrada.titulo)
                destino = en_titulo if all(any(p.startswith(t) for p in palabras(titulo)) for t in terminos) \
                    else en_otro_lado
                destino.agregar(entrada)
        for entrada in (*en_titulo, *en_otro_lado):
            if resultado.tamanio() >= limite:
                break
            resultado.agregar(entrada)
        return resultado

    def palabras_indexadas(self) -> int:
        """Palabras distintas en el trie."""
        return self._trie.tamanio()

    def nodos_del_trie(self) -> int:
        """Letras (nodos) que usa el trie: menos que la suma de las palabras, porque comparten prefijos."""
        return self._trie.cantidad_nodos()
