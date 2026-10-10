"""Lista simplemente enlazada."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

from bitcoinai.estructuras.excepciones import EstructuraVaciaError, IndiceFueraDeRangoError
from bitcoinai.estructuras.nodos import NodoSimple

if TYPE_CHECKING:
    from _typeshed import SupportsDunderLT


class Lista[T]:
    """Lista simplemente enlazada genérica, con referencias a la cabeza y a la cola.

    Agregar al inicio y al final cuesta O(1) gracias a esas dos referencias; el
    acceso por índice recorre desde la cabeza y cuesta O(n). En el proyecto
    registra las operaciones cerradas y las órdenes terminadas.
    Los índices válidos van de 0 a ``tamanio() - 1`` (no se aceptan negativos).
    """

    __slots__ = ("_cabeza", "_cola", "_tamanio")

    def __init__(self) -> None:
        """Crea una lista vacía. Complejidad: O(1)."""
        self._cabeza: NodoSimple[T] | None = None
        self._cola: NodoSimple[T] | None = None
        self._tamanio = 0

    def agregar(self, valor: T) -> None:
        """Agrega un elemento al final.

        Complejidad: O(1), gracias a la referencia a la cola.
        """
        nuevo = NodoSimple(valor)
        if self._cola is None:
            self._cabeza = nuevo
        else:
            self._cola._siguiente = nuevo
        self._cola = nuevo
        self._tamanio += 1

    def agregar_inicio(self, valor: T) -> None:
        """Agrega un elemento al inicio.

        Complejidad: O(1).
        """
        self._cabeza = NodoSimple(valor, self._cabeza)
        if self._cola is None:
            self._cola = self._cabeza
        self._tamanio += 1

    def insertar_ordenado(self, valor: T, clave: Callable[[T], SupportsDunderLT[Any]]) -> None:
        """Inserta manteniendo el orden según ``clave`` (como en ``sorted``).

        Si hay elementos con la misma clave, el nuevo queda después de ellos
        (inserción estable). Supone que la lista ya está ordenada con esa clave.
        Complejidad: O(n), porque puede recorrer toda la lista.
        """
        clave_nueva = clave(valor)
        if self._cabeza is None or clave_nueva < clave(self._cabeza._valor):
            self.agregar_inicio(valor)
            return
        actual = self._cabeza
        while actual._siguiente is not None and not clave_nueva < clave(actual._siguiente._valor):
            actual = actual._siguiente
        nuevo = NodoSimple(valor, actual._siguiente)
        actual._siguiente = nuevo
        if actual is self._cola:
            self._cola = nuevo
        self._tamanio += 1

    def obtener(self, indice: int) -> T:
        """Devuelve el elemento en la posición indicada.

        Complejidad: O(n) en general; O(1) para el primero y el último.

        Raises:
            IndiceFueraDeRangoError: si el índice no existe.
        """
        self._validar_indice(indice)
        return self._nodo_en(indice)._valor

    def eliminar(self, indice: int) -> T:
        """Elimina el elemento en la posición indicada y lo devuelve.

        Complejidad: O(n), porque hay que llegar al nodo anterior; O(1) para el primero.

        Raises:
            IndiceFueraDeRangoError: si el índice no existe.
        """
        self._validar_indice(indice)
        if indice == 0:
            assert self._cabeza is not None
            eliminado = self._cabeza
            self._cabeza = eliminado._siguiente
            if self._cabeza is None:
                self._cola = None
        else:
            anterior = self._nodo_en(indice - 1)
            assert anterior._siguiente is not None
            eliminado = anterior._siguiente
            anterior._siguiente = eliminado._siguiente
            if eliminado is self._cola:
                self._cola = anterior
        self._tamanio -= 1
        return eliminado._valor

    def buscar(self, condicion: Callable[[T], bool]) -> int:
        """Devuelve el índice del primer elemento que cumple la condición, o -1.

        Complejidad: O(n).
        """
        indice = 0
        actual = self._cabeza
        while actual is not None:
            if condicion(actual._valor):
                return indice
            actual = actual._siguiente
            indice += 1
        return -1

    def primero(self) -> T:
        """Devuelve el primer elemento sin quitarlo.

        Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si la lista está vacía.
        """
        if self._cabeza is None:
            raise EstructuraVaciaError("La lista está vacía")
        return self._cabeza._valor

    def ultimo(self) -> T:
        """Devuelve el último elemento sin quitarlo.

        Complejidad: O(1), gracias a la referencia a la cola.

        Raises:
            EstructuraVaciaError: si la lista está vacía.
        """
        if self._cola is None:
            raise EstructuraVaciaError("La lista está vacía")
        return self._cola._valor

    def tamanio(self) -> int:
        """Cantidad de elementos. Complejidad: O(1), porque se lleva un contador."""
        return self._tamanio

    def esta_vacia(self) -> bool:
        """Indica si no hay elementos. Complejidad: O(1)."""
        return self._tamanio == 0

    def vaciar(self) -> None:
        """Quita todos los elementos. Complejidad: O(1); el recolector libera los nodos."""
        self._cabeza = None
        self._cola = None
        self._tamanio = 0

    def __iter__(self) -> Iterator[T]:
        """Recorre de la cabeza a la cola (para usar ``for``).

        Complejidad: O(1) por paso; O(n) el recorrido completo.
        """
        actual = self._cabeza
        while actual is not None:
            yield actual._valor
            actual = actual._siguiente

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar, por ejemplo ``Lista(1, 2, 3)``. Complejidad: O(n)."""
        return "Lista(" + ", ".join(repr(valor) for valor in self) + ")"

    def _nodo_en(self, indice: int) -> NodoSimple[T]:
        """Nodo en una posición ya validada. O(n); O(1) para el último."""
        if indice == self._tamanio - 1:
            assert self._cola is not None
            return self._cola
        actual = self._cabeza
        for _ in range(indice):
            assert actual is not None
            actual = actual._siguiente
        assert actual is not None
        return actual

    def _validar_indice(self, indice: int) -> None:
        if not 0 <= indice < self._tamanio:
            raise IndiceFueraDeRangoError(indice, self._tamanio)
