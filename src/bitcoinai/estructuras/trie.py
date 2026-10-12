"""Trie (árbol de prefijos) para buscar palabras mientras se escriben."""

from __future__ import annotations

from collections.abc import Iterator

from bitcoinai.estructuras.excepciones import EstructuraVaciaError
from bitcoinai.estructuras.lista import Lista
from bitcoinai.estructuras.pila import Pila


class NodoTrie[V]:
    """Una letra del trie.

    Los hijos van en una lista enlazada de hermanos ordenada por letra
    (representación "primer hijo, siguiente hermano"): no hace falta un mapa, y
    el recorrido sale en orden alfabético.
    """

    __slots__ = ("hermano", "hijo", "letra", "tiene_valor", "valor")

    def __init__(self, letra: str) -> None:
        self.letra = letra
        self.hijo: NodoTrie[V] | None = None
        self.hermano: NodoTrie[V] | None = None
        self.tiene_valor = False
        self.valor: V | None = None

    def hijos(self) -> Iterator[NodoTrie[V]]:
        """Los hijos en orden alfabético (para dibujar el trie). Complejidad: O(a)."""
        hijo = self.hijo
        while hijo is not None:
            yield hijo
            hijo = hijo.hermano


class Trie[V]:
    """Mapa ``palabra → valor`` que encuentra todas las palabras que empiezan igual.

    Cada nodo es una letra; una palabra es el camino desde la raíz. Las palabras
    que comparten prefijo comparten nodos ("orden" y "órdenes" normalizadas
    comparten "orden"). Buscar o insertar cuesta O(m·a), con m letras y a el
    número de hermanos que se revisan en cada nivel (pocos: el alfabeto es chico).
    Lo importante: no depende de cuántas palabras haya guardadas.

    En el proyecto responde la búsqueda de Ctrl + K mientras se escribe.
    """

    __slots__ = ("_nodos", "_raiz", "_tamanio")

    def __init__(self) -> None:
        """Crea un trie vacío. Complejidad: O(1)."""
        self._raiz: NodoTrie[V] = NodoTrie("")
        self._tamanio = 0
        self._nodos = 1

    def _hijo(self, nodo: NodoTrie[V], letra: str) -> NodoTrie[V] | None:
        """El hijo con esa letra, o ``None``. Los hermanos están ordenados: para antes. O(a)."""
        hijo = nodo.hijo
        while hijo is not None and hijo.letra < letra:
            hijo = hijo.hermano
        return hijo if hijo is not None and hijo.letra == letra else None

    def _hijo_o_nuevo(self, nodo: NodoTrie[V], letra: str) -> NodoTrie[V]:
        """El hijo con esa letra; si no existe, lo crea en su lugar alfabético. O(a)."""
        anterior: NodoTrie[V] | None = None
        hijo = nodo.hijo
        while hijo is not None and hijo.letra < letra:
            anterior, hijo = hijo, hijo.hermano
        if hijo is not None and hijo.letra == letra:
            return hijo
        nuevo: NodoTrie[V] = NodoTrie(letra)
        nuevo.hermano = hijo
        if anterior is None:
            nodo.hijo = nuevo
        else:
            anterior.hermano = nuevo
        self._nodos += 1
        return nuevo

    def _nodo_de(self, texto: str) -> NodoTrie[V] | None:
        nodo: NodoTrie[V] | None = self._raiz
        for letra in texto:
            assert nodo is not None
            nodo = self._hijo(nodo, letra)
            if nodo is None:
                return None
        return nodo

    def insertar(self, palabra: str, valor: V) -> bool:
        """Guarda la palabra con su valor; si ya estaba, cambia el valor.

        Complejidad: O(m·a).

        Returns:
            True si la palabra era nueva.

        Raises:
            ValueError: si la palabra está vacía.
        """
        if not palabra:
            raise ValueError("La palabra no puede estar vacía")
        nodo = self._raiz
        for letra in palabra:
            nodo = self._hijo_o_nuevo(nodo, letra)
        nueva = not nodo.tiene_valor
        nodo.tiene_valor, nodo.valor = True, valor
        self._tamanio += int(nueva)
        return nueva

    def buscar(self, palabra: str) -> V | None:
        """Valor de la palabra exacta, o ``None``. Complejidad: O(m·a)."""
        nodo = self._nodo_de(palabra)
        return nodo.valor if nodo is not None and nodo.tiene_valor else None

    def contiene(self, palabra: str) -> bool:
        """Indica si la palabra exacta está. Complejidad: O(m·a)."""
        nodo = self._nodo_de(palabra)
        return nodo is not None and nodo.tiene_valor

    def hay_prefijo(self, prefijo: str) -> bool:
        """Indica si alguna palabra empieza así. Complejidad: O(m·a)."""
        return self._nodo_de(prefijo) is not None

    def con_prefijo(self, prefijo: str, limite: int = 10) -> Lista[tuple[str, V]]:
        """Hasta ``limite`` palabras que empiezan con ``prefijo``, en orden alfabético.

        Baja hasta el nodo del prefijo y desde ahí recorre en profundidad con una
        pila propia, cortando al juntar ``limite``. Complejidad: O(m·a + nodos visitados).
        """
        resultado: Lista[tuple[str, V]] = Lista()
        inicio = self._nodo_de(prefijo)
        if inicio is None or limite <= 0:
            return resultado
        pendientes: Pila[tuple[NodoTrie[V], str]] = Pila()
        pendientes.apilar((inicio, prefijo))
        while not pendientes.esta_vacia() and resultado.tamanio() < limite:
            nodo, texto = pendientes.desapilar()
            if nodo.tiene_valor:
                resultado.agregar((texto, nodo.valor))  # type: ignore[arg-type]
            # Los hijos se apilan al revés para que salga primero la letra menor.
            hijos: Pila[NodoTrie[V]] = Pila()
            hijo = nodo.hijo
            while hijo is not None:
                hijos.apilar(hijo)
                hijo = hijo.hermano
            while not hijos.esta_vacia():
                h = hijos.desapilar()
                pendientes.apilar((h, texto + h.letra))
        return resultado

    def eliminar(self, palabra: str) -> bool:
        """Quita la palabra y los nodos que quedan sin uso. Complejidad: O(m·a).

        Returns:
            True si estaba.
        """
        camino: Pila[NodoTrie[V]] = Pila()
        nodo: NodoTrie[V] | None = self._raiz
        for letra in palabra:
            assert nodo is not None
            camino.apilar(nodo)
            nodo = self._hijo(nodo, letra)
            if nodo is None:
                return False
        if nodo is None or not nodo.tiene_valor:
            return False
        nodo.tiene_valor, nodo.valor = False, None
        self._tamanio -= 1
        # Sube quitando hojas vacías: una letra sin hijos y que no termina palabra sobra.
        while not camino.esta_vacia() and nodo.hijo is None and not nodo.tiene_valor:
            padre = camino.desapilar()
            self._quitar_hijo(padre, nodo)
            nodo = padre
        return True

    def _quitar_hijo(self, padre: NodoTrie[V], hijo: NodoTrie[V]) -> None:
        if padre.hijo is hijo:
            padre.hijo = hijo.hermano
        else:
            anterior = padre.hijo
            while anterior is not None and anterior.hermano is not hijo:
                anterior = anterior.hermano
            if anterior is not None:
                anterior.hermano = hijo.hermano
        self._nodos -= 1

    def primera(self) -> str:
        """La palabra menor en orden alfabético. Complejidad: O(longitud·a).

        Raises:
            EstructuraVaciaError: si el trie está vacío.
        """
        primera = self.con_prefijo("", 1)
        if primera.esta_vacia():
            raise EstructuraVaciaError("El trie está vacío")
        return primera.obtener(0)[0]

    def raiz(self) -> NodoTrie[V]:
        """La raíz (letra vacía), para recorrer y dibujar el trie sin cambiarlo. Complejidad: O(1)."""
        return self._raiz

    def cantidad_nodos(self) -> int:
        """Nodos (letras) que usa, contando la raíz: muestra cuánto comparten los prefijos. Complejidad: O(1)."""
        return self._nodos

    def tamanio(self) -> int:
        """Cantidad de palabras. Complejidad: O(1)."""
        return self._tamanio

    def esta_vacio(self) -> bool:
        """Indica si no hay palabras. Complejidad: O(1)."""
        return self._tamanio == 0

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar. Complejidad: O(1)."""
        return f"Trie(tamanio={self._tamanio}, nodos={self._nodos})"
