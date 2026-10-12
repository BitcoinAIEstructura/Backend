"""Arreglo de tamaño fijo, como ``new T[n]`` en Java."""

from __future__ import annotations

import ctypes
from collections.abc import Iterator
from typing import Any, cast

from bitcoinai.estructuras.excepciones import IndiceFueraDeRangoError


class Arreglo[T]:
    """Bloque de ``capacidad`` casillas contiguas con acceso por índice en O(1).

    Es la pieza que falta para el montículo, la cola circular y la tabla hash:
    todas necesitan saltar directo a la casilla ``i`` sin recorrer nodos. Por
    dentro es un arreglo de punteros de C (``ctypes.py_object * n``), no una
    ``list``: no crece, no se encoge y no tiene ``append``. Para "agrandarlo" hay
    que crear otro más grande y copiar, igual que en Java.

    Cada casilla empieza en ``None`` (casilla vacía).
    """

    __slots__ = ("_capacidad", "_casillas")

    def __init__(self, capacidad: int) -> None:
        """Crea un arreglo con ``capacidad`` casillas vacías.

        Complejidad: O(n), porque deja cada casilla en ``None``.

        Raises:
            ValueError: si la capacidad es negativa.
        """
        if capacidad < 0:
            raise ValueError(f"La capacidad no puede ser negativa: {capacidad}")
        self._capacidad = capacidad
        casillas: Any = (ctypes.py_object * capacidad)()
        for i in range(capacidad):
            casillas[i] = None
        self._casillas: Any = casillas

    def _revisar(self, indice: int) -> None:
        if not 0 <= indice < self._capacidad:
            raise IndiceFueraDeRangoError(indice, self._capacidad)

    def obtener(self, indice: int) -> T | None:
        """Valor de la casilla (``None`` si está vacía). Complejidad: O(1).

        Raises:
            IndiceFueraDeRangoError: si el índice no está entre 0 y ``capacidad() - 1``.
        """
        self._revisar(indice)
        return cast("T | None", self._casillas[indice])

    def poner(self, indice: int, valor: T | None) -> None:
        """Guarda un valor en la casilla (``None`` la vacía). Complejidad: O(1).

        Raises:
            IndiceFueraDeRangoError: si el índice no está entre 0 y ``capacidad() - 1``.
        """
        self._revisar(indice)
        self._casillas[indice] = valor

    def intercambiar(self, i: int, j: int) -> None:
        """Intercambia dos casillas. Complejidad: O(1)."""
        self._revisar(i)
        self._revisar(j)
        self._casillas[i], self._casillas[j] = self._casillas[j], self._casillas[i]

    def capacidad(self) -> int:
        """Cantidad de casillas (no cambia nunca). Complejidad: O(1)."""
        return self._capacidad

    def copiar_en(self, destino: Arreglo[T], cantidad: int) -> None:
        """Copia las primeras ``cantidad`` casillas en ``destino`` (para crecer). Complejidad: O(cantidad)."""
        for i in range(cantidad):
            destino.poner(i, self.obtener(i))

    def __len__(self) -> int:
        """Igual que ``capacidad()``. Complejidad: O(1)."""
        return self._capacidad

    def __iter__(self) -> Iterator[T | None]:
        """Recorre las casillas de la 0 a la última, vacías incluidas. Complejidad: O(n)."""
        for i in range(self._capacidad):
            yield self.obtener(i)

    def __repr__(self) -> str:
        """Representación para depurar, por ejemplo ``Arreglo(capacidad=8)``. Complejidad: O(1)."""
        return f"Arreglo(capacidad={self._capacidad})"
