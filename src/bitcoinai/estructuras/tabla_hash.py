"""Tabla hash con encadenamiento separado, sobre un Arreglo de cubetas."""

from __future__ import annotations

from collections.abc import Hashable, Iterator

from bitcoinai.estructuras.arreglo import Arreglo
from bitcoinai.estructuras.lista import Lista

CAPACIDAD_INICIAL = 8
FACTOR_MAXIMO = 0.75
"""Si hay más de 0,75 elementos por cubeta en promedio, la tabla crece al doble."""


class _Entrada[K, V]:
    """Un par clave-valor y la siguiente entrada de la misma cubeta (una lista enlazada)."""

    __slots__ = ("clave", "siguiente", "valor")

    def __init__(self, clave: K, valor: V, siguiente: _Entrada[K, V] | None) -> None:
        self.clave = clave
        self.valor = valor
        self.siguiente = siguiente


class TablaHash[K: Hashable, V]:
    """Mapa ``clave → valor`` con poner, obtener y eliminar en O(1) en promedio.

    El hash de la clave elige una cubeta del arreglo (``hash & (capacidad - 1)``;
    la capacidad siempre es potencia de 2). Las claves que caen en la misma cubeta
    (una colisión) se encadenan en una lista enlazada. Mientras el factor de carga
    (elementos ÷ cubetas) no pase de 0,75, las cadenas son cortas y cada operación
    revisa en promedio uno o dos nodos. Al pasarlo, se crea un arreglo del doble y
    se reubica cada entrada (rehash): O(n), pero pasa pocas veces, así que el costo
    amortizado por inserción sigue siendo O(1).

    En el proyecto guarda la simulación de cada usuario por su id.
    """

    __slots__ = ("_cubetas", "_tamanio")

    def __init__(self, capacidad: int = CAPACIDAD_INICIAL) -> None:
        """Crea una tabla vacía (la capacidad se sube a la potencia de 2 siguiente). Complejidad: O(capacidad)."""
        cubetas = 1
        while cubetas < capacidad:
            cubetas *= 2
        self._cubetas: Arreglo[_Entrada[K, V]] = Arreglo(cubetas)
        self._tamanio = 0

    def _cubeta(self, clave: K, capacidad: int) -> int:
        """Índice de la cubeta. Mezcla los bits altos con los bajos para que claves
        seguidas (ids 1, 2, 3…) o múltiplos de la capacidad no se amontonen. Complejidad: O(1)."""
        h = hash(clave)
        h ^= h >> 16
        return h & (capacidad - 1)

    def _buscar(self, clave: K) -> _Entrada[K, V] | None:
        entrada = self._cubetas.obtener(self._cubeta(clave, self._cubetas.capacidad()))
        while entrada is not None:
            if entrada.clave == clave:
                return entrada
            entrada = entrada.siguiente
        return None

    def poner(self, clave: K, valor: V) -> bool:
        """Guarda el valor; si la clave ya estaba, lo cambia.

        Complejidad: O(1) en promedio (O(n) cuando toca crecer, O(1) amortizado).

        Returns:
            True si la clave era nueva.
        """
        existente = self._buscar(clave)
        if existente is not None:
            existente.valor = valor
            return False
        if (self._tamanio + 1) / self._cubetas.capacidad() > FACTOR_MAXIMO:
            self._crecer()
        i = self._cubeta(clave, self._cubetas.capacidad())
        self._cubetas.poner(i, _Entrada(clave, valor, self._cubetas.obtener(i)))
        self._tamanio += 1
        return True

    def _crecer(self) -> None:
        """Duplica las cubetas y reubica cada entrada según su hash. Complejidad: O(n)."""
        nuevas: Arreglo[_Entrada[K, V]] = Arreglo(self._cubetas.capacidad() * 2)
        for cabeza in self._cubetas:
            entrada = cabeza
            while entrada is not None:
                siguiente = entrada.siguiente
                i = self._cubeta(entrada.clave, nuevas.capacidad())
                entrada.siguiente = nuevas.obtener(i)
                nuevas.poner(i, entrada)
                entrada = siguiente
        self._cubetas = nuevas

    def obtener(self, clave: K) -> V | None:
        """Valor de la clave, o ``None`` si no está. Complejidad: O(1) en promedio."""
        entrada = self._buscar(clave)
        return None if entrada is None else entrada.valor

    def contiene(self, clave: K) -> bool:
        """Indica si la clave está. Complejidad: O(1) en promedio."""
        return self._buscar(clave) is not None

    def eliminar(self, clave: K) -> bool:
        """Quita la clave desenlazando su nodo de la cadena. Complejidad: O(1) en promedio.

        Returns:
            True si estaba.
        """
        i = self._cubeta(clave, self._cubetas.capacidad())
        anterior: _Entrada[K, V] | None = None
        entrada = self._cubetas.obtener(i)
        while entrada is not None:
            if entrada.clave == clave:
                if anterior is None:
                    self._cubetas.poner(i, entrada.siguiente)
                else:
                    anterior.siguiente = entrada.siguiente
                self._tamanio -= 1
                return True
            anterior, entrada = entrada, entrada.siguiente
        return False

    # ---------- recorridos ----------

    def elementos(self) -> Iterator[tuple[K, V]]:
        """Todos los pares, cubeta por cubeta (sin un orden útil). Complejidad: O(n + capacidad)."""
        for cabeza in self._cubetas:
            entrada = cabeza
            while entrada is not None:
                yield entrada.clave, entrada.valor
                entrada = entrada.siguiente

    def valores(self) -> Iterator[V]:
        """Todos los valores. Complejidad: O(n + capacidad)."""
        for _, valor in self.elementos():
            yield valor

    # ---------- estadísticas (para mostrar cómo está repartida) ----------

    def longitudes_de_cubetas(self) -> Lista[int]:
        """Cuántas entradas tiene cada cubeta, de la 0 a la última. Complejidad: O(n + capacidad)."""
        longitudes: Lista[int] = Lista()
        for cabeza in self._cubetas:
            cantidad, entrada = 0, cabeza
            while entrada is not None:
                cantidad += 1
                entrada = entrada.siguiente
            longitudes.agregar(cantidad)
        return longitudes

    def capacidad(self) -> int:
        """Cantidad de cubetas. Complejidad: O(1)."""
        return self._cubetas.capacidad()

    def factor_de_carga(self) -> float:
        """Elementos por cubeta en promedio (nunca pasa de 0,75). Complejidad: O(1)."""
        return self._tamanio / self._cubetas.capacidad()

    def tamanio(self) -> int:
        """Cantidad de pares guardados. Complejidad: O(1)."""
        return self._tamanio

    def esta_vacia(self) -> bool:
        """Indica si no hay pares. Complejidad: O(1)."""
        return self._tamanio == 0

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar. Complejidad: O(1)."""
        return f"TablaHash(tamanio={self._tamanio}, capacidad={self.capacidad()})"
