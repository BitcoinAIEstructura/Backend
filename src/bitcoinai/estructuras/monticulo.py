"""Montículo binario (cola de prioridad) sobre un Arreglo."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

from bitcoinai.estructuras.arreglo import Arreglo
from bitcoinai.estructuras.excepciones import EstructuraVaciaError

if TYPE_CHECKING:
    from _typeshed import SupportsDunderLT

CAPACIDAD_INICIAL = 8


class _Entrada[T]:
    """Un elemento con su clave ya calculada y su turno de llegada (para desempatar)."""

    __slots__ = ("clave", "turno", "valor")

    def __init__(self, valor: T, clave: SupportsDunderLT[Any], turno: int) -> None:
        self.valor = valor
        self.clave = clave
        self.turno = turno


class Monticulo[T]:
    """Montículo binario: siempre deja a mano el elemento de mayor prioridad.

    Es un árbol binario completo guardado en un ``Arreglo``, nivel por nivel: los
    hijos de la casilla ``i`` están en ``2i + 1`` y ``2i + 2`` y su padre en
    ``(i - 1) // 2``. Cada padre tiene prioridad sobre sus hijos, así que el tope
    es la casilla 0. Insertar y extraer suben o bajan un elemento por una sola
    rama: O(log n).

    - ``clave`` dice qué se compara (como en ``sorted``). Por defecto va primero la
      clave menor; con ``mayor_primero=True``, la mayor.
    - Con claves iguales sale primero el que llegó antes (es estable).
    - Si se llena, crea un arreglo del doble y copia: O(1) amortizado por inserción.

    En el proyecto arma el ranking: con un montículo de tamaño k se sacan los k
    mejores de n usuarios en O(n log k).
    """

    __slots__ = ("_arreglo", "_clave", "_intercambios", "_mayor_primero", "_tamanio", "_turno")

    def __init__(self, clave: Callable[[T], SupportsDunderLT[Any]], *, mayor_primero: bool = False,
                 capacidad: int = CAPACIDAD_INICIAL) -> None:
        """Crea un montículo vacío. Complejidad: O(capacidad)."""
        self._arreglo: Arreglo[_Entrada[T]] = Arreglo(max(1, capacidad))
        self._clave = clave
        self._mayor_primero = mayor_primero
        self._tamanio = 0
        self._turno = 0
        self._intercambios = 0

    # ---------- comparación ----------

    def _antes(self, a: _Entrada[T], b: _Entrada[T]) -> bool:
        """¿``a`` debe estar más arriba que ``b``? Complejidad: O(1)."""
        if a.clave < b.clave:
            return not self._mayor_primero
        if b.clave < a.clave:
            return self._mayor_primero
        return a.turno < b.turno

    def _entrada(self, i: int) -> _Entrada[T]:
        entrada = self._arreglo.obtener(i)
        assert entrada is not None  # las casillas 0..tamanio-1 siempre están llenas
        return entrada

    # ---------- operaciones ----------

    def insertar(self, valor: T) -> None:
        """Agrega un elemento y lo sube hasta su lugar.

        Complejidad: O(log n); O(n) solo cuando hay que duplicar el arreglo
        (O(1) amortizado por eso).
        """
        if self._tamanio == self._arreglo.capacidad():
            mas_grande: Arreglo[_Entrada[T]] = Arreglo(self._arreglo.capacidad() * 2)
            self._arreglo.copiar_en(mas_grande, self._tamanio)
            self._arreglo = mas_grande
        self._arreglo.poner(self._tamanio, _Entrada(valor, self._clave(valor), self._turno))
        self._turno += 1
        self._tamanio += 1
        self._intercambios = 0
        self._subir(self._tamanio - 1)

    def ver_tope(self) -> T:
        """El de mayor prioridad, sin quitarlo. Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si el montículo está vacío.
        """
        if self._tamanio == 0:
            raise EstructuraVaciaError("El montículo está vacío")
        return self._entrada(0).valor

    def extraer(self) -> T:
        """Quita y devuelve el de mayor prioridad.

        El último elemento pasa a la raíz y baja hasta su lugar. Complejidad: O(log n).

        Raises:
            EstructuraVaciaError: si el montículo está vacío.
        """
        if self._tamanio == 0:
            raise EstructuraVaciaError("El montículo está vacío")
        tope = self._entrada(0).valor
        self._tamanio -= 1
        self._arreglo.intercambiar(0, self._tamanio)
        self._arreglo.poner(self._tamanio, None)
        self._intercambios = 0
        self._bajar(0)
        return tope

    def reemplazar_tope(self, valor: T) -> T:
        """Saca el tope y mete ``valor`` en un solo paso (para quedarse con los k mejores).

        Complejidad: O(log n), más barato que extraer e insertar por separado.

        Raises:
            EstructuraVaciaError: si el montículo está vacío.
        """
        if self._tamanio == 0:
            raise EstructuraVaciaError("El montículo está vacío")
        tope = self._entrada(0).valor
        self._arreglo.poner(0, _Entrada(valor, self._clave(valor), self._turno))
        self._turno += 1
        self._intercambios = 0
        self._bajar(0)
        return tope

    def _subir(self, i: int) -> None:
        """Intercambia con el padre mientras tenga más prioridad. Complejidad: O(log n)."""
        while i > 0:
            padre = (i - 1) // 2
            if not self._antes(self._entrada(i), self._entrada(padre)):
                return
            self._arreglo.intercambiar(i, padre)
            self._intercambios += 1
            i = padre

    def _bajar(self, i: int) -> None:
        """Intercambia con el hijo de más prioridad mientras haga falta. Complejidad: O(log n)."""
        while True:
            mejor = i
            for hijo in (2 * i + 1, 2 * i + 2):
                if hijo < self._tamanio and self._antes(self._entrada(hijo), self._entrada(mejor)):
                    mejor = hijo
            if mejor == i:
                return
            self._arreglo.intercambiar(i, mejor)
            self._intercambios += 1
            i = mejor

    # ---------- consultas ----------

    def tamanio(self) -> int:
        """Cantidad de elementos. Complejidad: O(1)."""
        return self._tamanio

    def esta_vacia(self) -> bool:
        """Indica si no hay elementos. Complejidad: O(1)."""
        return self._tamanio == 0

    def capacidad(self) -> int:
        """Casillas del arreglo de adentro (crece al doble cuando se llena). Complejidad: O(1)."""
        return self._arreglo.capacidad()

    def intercambios_ultima_operacion(self) -> int:
        """Cuántos intercambios hizo la última inserción o extracción (para mostrar cómo trabaja).

        Complejidad: O(1).
        """
        return self._intercambios

    def en_orden_de_arreglo(self) -> Iterator[T]:
        """Los elementos tal como están en el arreglo (nivel por nivel), no ordenados.

        Sirve para dibujar el árbol. Complejidad: O(n).
        """
        for i in range(self._tamanio):
            yield self._entrada(i).valor

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar, por ejemplo ``Monticulo(tamanio=3)``. Complejidad: O(1)."""
        return f"Monticulo(tamanio={self._tamanio})"
