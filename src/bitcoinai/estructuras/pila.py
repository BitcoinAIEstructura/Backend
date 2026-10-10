"""Pila LIFO con nodos enlazados."""

from __future__ import annotations

from bitcoinai.estructuras.excepciones import EstructuraVaciaError
from bitcoinai.estructuras.nodos import NodoSimple


class Pila[T]:
    """Pila genérica LIFO (el último en entrar es el primero en salir).

    Usa nodos simples con una referencia al tope: se apila y se desapila
    siempre por el tope, así que todas las operaciones cuestan O(1). En el
    proyecto guarda el historial de eventos y de decisiones, con el más
    reciente arriba.
    """

    __slots__ = ("_tamanio", "_tope")

    def __init__(self) -> None:
        """Crea una pila vacía. Complejidad: O(1)."""
        self._tope: NodoSimple[T] | None = None
        self._tamanio = 0

    def apilar(self, valor: T) -> None:
        """Pone un elemento en el tope.

        Complejidad: O(1).
        """
        self._tope = NodoSimple(valor, self._tope)
        self._tamanio += 1

    def desapilar(self) -> T:
        """Quita y devuelve el elemento del tope (el último apilado).

        Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si la pila está vacía.
        """
        if self._tope is None:
            raise EstructuraVaciaError("La pila está vacía")
        valor = self._tope._valor
        self._tope = self._tope._siguiente
        self._tamanio -= 1
        return valor

    def ver_tope(self) -> T:
        """Devuelve el elemento del tope sin quitarlo.

        Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si la pila está vacía.
        """
        if self._tope is None:
            raise EstructuraVaciaError("La pila está vacía")
        return self._tope._valor

    def tamanio(self) -> int:
        """Cantidad de elementos. Complejidad: O(1), porque se lleva un contador."""
        return self._tamanio

    def esta_vacia(self) -> bool:
        """Indica si no hay elementos. Complejidad: O(1)."""
        return self._tamanio == 0

    def vaciar(self) -> None:
        """Quita todos los elementos. Complejidad: O(1); el recolector libera los nodos."""
        self._tope = None
        self._tamanio = 0

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar, por ejemplo ``Pila(tamanio=3)``. Complejidad: O(1)."""
        return f"Pila(tamanio={self._tamanio})"
