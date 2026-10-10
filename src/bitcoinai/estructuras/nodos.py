"""Nodos de las estructuras enlazadas.

Los atributos con guion bajo (``_siguiente``, ``_anterior``…) solo los
modifican las estructuras de este paquete, para que nadie de fuera pueda romper
sus enlaces. Desde fuera se leen con las propiedades públicas.
"""

from __future__ import annotations


class NodoSimple[T]:
    """Nodo de una estructura simplemente enlazada: un valor y el nodo siguiente.

    Lo usan ``Lista``, ``Cola`` y ``Pila``.
    """

    __slots__ = ("_siguiente", "_valor")

    def __init__(self, valor: T, siguiente: NodoSimple[T] | None = None) -> None:
        """Crea el nodo, opcionalmente enlazado a otro.

        Complejidad: O(1).
        """
        self._valor = valor
        self._siguiente = siguiente

    @property
    def valor(self) -> T:
        """Valor guardado. Complejidad: O(1)."""
        return self._valor

    @property
    def siguiente(self) -> NodoSimple[T] | None:
        """Nodo siguiente, o ``None`` si es el último. Complejidad: O(1)."""
        return self._siguiente


class NodoDoble[T]:
    """Nodo de una estructura doblemente enlazada: un valor, el anterior y el siguiente.

    Lo usa ``ListaDoble``. Además recuerda a qué lista pertenece y en qué
    "generación" de esa lista se creó; así ``ListaDoble.eliminar_nodo`` puede
    comprobar en O(1) que el nodo sigue en la lista antes de quitarlo.
    """

    __slots__ = ("_anterior", "_generacion", "_lista", "_siguiente", "_valor")

    def __init__(self, valor: T) -> None:
        """Crea el nodo sin enlaces y sin lista.

        Complejidad: O(1).
        """
        self._valor = valor
        self._anterior: NodoDoble[T] | None = None
        self._siguiente: NodoDoble[T] | None = None
        self._lista: object | None = None
        self._generacion = 0

    @property
    def valor(self) -> T:
        """Valor guardado. Complejidad: O(1)."""
        return self._valor

    @property
    def anterior(self) -> NodoDoble[T] | None:
        """Nodo anterior, o ``None`` si es el primero. Complejidad: O(1)."""
        return self._anterior

    @property
    def siguiente(self) -> NodoDoble[T] | None:
        """Nodo siguiente, o ``None`` si es el último. Complejidad: O(1)."""
        return self._siguiente
