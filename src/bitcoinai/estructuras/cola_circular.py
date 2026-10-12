"""Cola circular (búfer de anillo) de capacidad fija sobre un Arreglo."""

from __future__ import annotations

from collections.abc import Iterator

from bitcoinai.estructuras.arreglo import Arreglo
from bitcoinai.estructuras.excepciones import EstructuraVaciaError, IndiceFueraDeRangoError


class ColaLlenaError(Exception):
    """Se lanza al encolar en una cola circular llena (con ``encolar``; ``agregar`` sobrescribe)."""


class ColaCircular[T]:
    """Cola FIFO de capacidad fija que reutiliza sus casillas dando la vuelta.

    Guarda el índice del frente y la cantidad de elementos; el final se calcula
    como ``(frente + tamaño) % capacidad``. Al llegar a la última casilla vuelve a
    la 0, así que nunca hay que mover elementos: todo es O(1) y la memoria no crece.

    - ``encolar`` falla si está llena (``ColaLlenaError``).
    - ``agregar`` sobrescribe el más viejo si está llena: así se guardan "los
      últimos N", como los últimos precios del mercado.

    En el proyecto guarda los últimos precios que manda el tiempo real.
    """

    __slots__ = ("_casillas", "_frente", "_tamanio")

    def __init__(self, capacidad: int) -> None:
        """Crea una cola vacía. Complejidad: O(capacidad).

        Raises:
            ValueError: si la capacidad no es positiva.
        """
        if capacidad <= 0:
            raise ValueError(f"La capacidad debe ser positiva: {capacidad}")
        self._casillas: Arreglo[T] = Arreglo(capacidad)
        self._frente = 0
        self._tamanio = 0

    def _indice(self, desplazamiento: int) -> int:
        return (self._frente + desplazamiento) % self._casillas.capacidad()

    def encolar(self, valor: T) -> None:
        """Agrega al final. Complejidad: O(1).

        Raises:
            ColaLlenaError: si no queda espacio.
        """
        if self.esta_llena():
            raise ColaLlenaError(f"La cola circular está llena ({self.capacidad()} elementos)")
        self._casillas.poner(self._indice(self._tamanio), valor)
        self._tamanio += 1

    def agregar(self, valor: T) -> T | None:
        """Agrega al final; si está llena, pisa al más viejo y lo devuelve. Complejidad: O(1)."""
        if not self.esta_llena():
            self.encolar(valor)
            return None
        pisado = self._casillas.obtener(self._frente)
        self._casillas.poner(self._frente, valor)
        self._frente = self._indice(1)
        return pisado

    def desencolar(self) -> T:
        """Quita y devuelve el más viejo. Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si está vacía.
        """
        if self._tamanio == 0:
            raise EstructuraVaciaError("La cola circular está vacía")
        valor = self._casillas.obtener(self._frente)
        self._casillas.poner(self._frente, None)
        self._frente = self._indice(1)
        self._tamanio -= 1
        return valor  # type: ignore[return-value]  # las casillas ocupadas nunca son None

    def ver_frente(self) -> T:
        """El más viejo, sin quitarlo. Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si está vacía.
        """
        return self.obtener(0) if self._tamanio else self._vacia()

    def ver_final(self) -> T:
        """El más nuevo, sin quitarlo. Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si está vacía.
        """
        return self.obtener(self._tamanio - 1) if self._tamanio else self._vacia()

    def _vacia(self) -> T:
        raise EstructuraVaciaError("La cola circular está vacía")

    def obtener(self, posicion: int) -> T:
        """El elemento en la posición dada, contando desde el más viejo (0). Complejidad: O(1).

        Raises:
            IndiceFueraDeRangoError: si la posición no está entre 0 y ``tamanio() - 1``.
        """
        if not 0 <= posicion < self._tamanio:
            raise IndiceFueraDeRangoError(posicion, self._tamanio)
        return self._casillas.obtener(self._indice(posicion))  # type: ignore[return-value]

    def __iter__(self) -> Iterator[T]:
        """Del más viejo al más nuevo. Complejidad: O(n)."""
        for posicion in range(self._tamanio):
            yield self.obtener(posicion)

    def casillas(self) -> Iterator[T | None]:
        """Las casillas tal como están en memoria (con huecos), para dibujar el anillo. Complejidad: O(capacidad)."""
        yield from self._casillas

    def indice_frente(self) -> int:
        """Casilla donde está el más viejo. Complejidad: O(1)."""
        return self._frente

    def capacidad(self) -> int:
        """Casillas del anillo. Complejidad: O(1)."""
        return self._casillas.capacidad()

    def tamanio(self) -> int:
        """Cantidad de elementos. Complejidad: O(1)."""
        return self._tamanio

    def esta_vacia(self) -> bool:
        """Indica si no hay elementos. Complejidad: O(1)."""
        return self._tamanio == 0

    def esta_llena(self) -> bool:
        """Indica si no queda espacio. Complejidad: O(1)."""
        return self._tamanio == self._casillas.capacidad()

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar. Complejidad: O(1)."""
        return f"ColaCircular(tamanio={self._tamanio}, capacidad={self.capacidad()})"
