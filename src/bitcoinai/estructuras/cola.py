"""Cola FIFO con nodos enlazados."""

from __future__ import annotations

from bitcoinai.estructuras.excepciones import EstructuraVaciaError
from bitcoinai.estructuras.nodos import NodoSimple


class Cola[T]:
    """Cola genérica FIFO (el primero en entrar es el primero en salir).

    Usa nodos simples con referencias al frente y al final: se encola por el
    final y se desencola por el frente, así que todas las operaciones cuestan
    O(1). En el proyecto guarda las órdenes pendientes.
    """

    __slots__ = ("_fin", "_frente", "_tamanio")

    def __init__(self) -> None:
        """Crea una cola vacía. Complejidad: O(1)."""
        self._frente: NodoSimple[T] | None = None
        self._fin: NodoSimple[T] | None = None
        self._tamanio = 0

    def encolar(self, valor: T) -> None:
        """Agrega un elemento al final.

        Complejidad: O(1), gracias a la referencia al final.
        """
        nuevo = NodoSimple(valor)
        if self._fin is None:
            self._frente = nuevo
        else:
            self._fin._siguiente = nuevo
        self._fin = nuevo
        self._tamanio += 1

    def desencolar(self) -> T:
        """Quita y devuelve el elemento del frente (el más antiguo).

        Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si la cola está vacía.
        """
        if self._frente is None:
            raise EstructuraVaciaError("La cola está vacía")
        valor = self._frente._valor
        self._frente = self._frente._siguiente
        if self._frente is None:
            self._fin = None
        self._tamanio -= 1
        return valor

    def ver_frente(self) -> T:
        """Devuelve el elemento del frente sin quitarlo.

        Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si la cola está vacía.
        """
        if self._frente is None:
            raise EstructuraVaciaError("La cola está vacía")
        return self._frente._valor

    def tamanio(self) -> int:
        """Cantidad de elementos. Complejidad: O(1), porque se lleva un contador."""
        return self._tamanio

    def esta_vacia(self) -> bool:
        """Indica si no hay elementos. Complejidad: O(1)."""
        return self._tamanio == 0

    def vaciar(self) -> None:
        """Quita todos los elementos. Complejidad: O(1); el recolector libera los nodos."""
        self._frente = None
        self._fin = None
        self._tamanio = 0

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar, por ejemplo ``Cola(tamanio=3)``. Complejidad: O(1)."""
        return f"Cola(tamanio={self._tamanio})"
