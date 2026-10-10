"""Lista doblemente enlazada."""

from __future__ import annotations

from collections.abc import Iterator

from bitcoinai.estructuras.excepciones import EstructuraVaciaError, IndiceFueraDeRangoError
from bitcoinai.estructuras.nodos import NodoDoble


class ListaDoble[T]:
    """Lista doblemente enlazada genérica con referencias a la cabeza y a la cola.

    Cada nodo conoce a su anterior y a su siguiente, así que se puede agregar y
    quitar en ambos extremos en O(1), recorrer en los dos sentidos, llegar a un
    índice desde el extremo más cercano y quitar un nodo conocido en O(1).

    En el proyecto guarda la ventana de velas (las nuevas entran por el final y
    las más antiguas salen por el inicio con ``conservar_ultimos``) y los
    clientes conectados al tiempo real (se quitan por su nodo con ``eliminar_nodo``).
    Los índices válidos van de 0 a ``tamanio() - 1`` (no se aceptan negativos).
    """

    __slots__ = ("_cabeza", "_cola", "_generacion", "_tamanio")

    def __init__(self) -> None:
        """Crea una lista vacía. Complejidad: O(1)."""
        self._cabeza: NodoDoble[T] | None = None
        self._cola: NodoDoble[T] | None = None
        self._tamanio = 0
        # Aumenta en cada vaciar(), para invalidar en O(1) los nodos que había antes.
        self._generacion = 0

    # ---------- agregar ----------

    def agregar_inicio(self, valor: T) -> None:
        """Agrega un elemento al inicio.

        Complejidad: O(1).
        """
        nuevo = self._crear_nodo(valor)
        if self._cabeza is None:
            self._cola = nuevo
        else:
            nuevo._siguiente = self._cabeza
            self._cabeza._anterior = nuevo
        self._cabeza = nuevo
        self._tamanio += 1

    def agregar_final(self, valor: T) -> None:
        """Agrega un elemento al final.

        Complejidad: O(1).
        """
        self.agregar_final_nodo(valor)

    def agregar_final_nodo(self, valor: T) -> NodoDoble[T]:
        """Agrega un elemento al final y devuelve su nodo.

        Guardar el nodo permite quitarlo después en O(1) con ``eliminar_nodo``,
        sin buscarlo.
        Complejidad: O(1).
        """
        nuevo = self._crear_nodo(valor)
        if self._cola is None:
            self._cabeza = nuevo
        else:
            nuevo._anterior = self._cola
            self._cola._siguiente = nuevo
        self._cola = nuevo
        self._tamanio += 1
        return nuevo

    def insertar(self, indice: int, valor: T) -> None:
        """Inserta en la posición indicada; los que estaban desde ahí se corren a la derecha.

        Con ``indice == tamanio()`` agrega al final.
        Complejidad: O(min(i, n - i)), porque llega desde el extremo más cercano.

        Raises:
            IndiceFueraDeRangoError: si el índice no está entre 0 y ``tamanio()``.
        """
        if not 0 <= indice <= self._tamanio:
            raise IndiceFueraDeRangoError(indice, self._tamanio)
        if indice == 0:
            self.agregar_inicio(valor)
        elif indice == self._tamanio:
            self.agregar_final(valor)
        else:
            siguiente = self._nodo_en(indice)
            anterior = siguiente._anterior
            assert anterior is not None
            nuevo = self._crear_nodo(valor)
            nuevo._anterior = anterior
            nuevo._siguiente = siguiente
            anterior._siguiente = nuevo
            siguiente._anterior = nuevo
            self._tamanio += 1

    # ---------- leer ----------

    def obtener(self, indice: int) -> T:
        """Devuelve el elemento en la posición indicada, desde el extremo más cercano.

        Complejidad: O(min(i, n - i)); en el peor caso O(n/2).

        Raises:
            IndiceFueraDeRangoError: si el índice no existe.
        """
        self._validar_indice(indice)
        return self._nodo_en(indice)._valor

    def primero(self) -> T:
        """Devuelve el primer elemento sin quitarlo.

        Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si la lista está vacía.
        """
        if self._cabeza is None:
            raise EstructuraVaciaError("La lista doble está vacía")
        return self._cabeza._valor

    def ultimo(self) -> T:
        """Devuelve el último elemento sin quitarlo.

        Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si la lista está vacía.
        """
        if self._cola is None:
            raise EstructuraVaciaError("La lista doble está vacía")
        return self._cola._valor

    def tamanio(self) -> int:
        """Cantidad de elementos. Complejidad: O(1), porque se lleva un contador."""
        return self._tamanio

    def esta_vacia(self) -> bool:
        """Indica si no hay elementos. Complejidad: O(1)."""
        return self._tamanio == 0

    # ---------- quitar ----------

    def eliminar_primero(self) -> T:
        """Quita y devuelve el primer elemento.

        Complejidad: O(1).

        Raises:
            EstructuraVaciaError: si la lista está vacía.
        """
        if self._cabeza is None:
            raise EstructuraVaciaError("La lista doble está vacía")
        return self._desenlazar(self._cabeza)

    def eliminar_ultimo(self) -> T:
        """Quita y devuelve el último elemento.

        Complejidad: O(1), porque la cola conoce a su anterior.

        Raises:
            EstructuraVaciaError: si la lista está vacía.
        """
        if self._cola is None:
            raise EstructuraVaciaError("La lista doble está vacía")
        return self._desenlazar(self._cola)

    def eliminar(self, indice: int) -> T:
        """Quita y devuelve el elemento en la posición indicada.

        Complejidad: O(min(i, n - i)) para llegar al nodo; desenlazarlo es O(1).

        Raises:
            IndiceFueraDeRangoError: si el índice no existe.
        """
        self._validar_indice(indice)
        return self._desenlazar(self._nodo_en(indice))

    def eliminar_nodo(self, nodo: NodoDoble[T] | None) -> bool:
        """Quita un nodo de la lista sin recorrerla.

        Como el nodo conoce a su anterior y a su siguiente, basta con unirlos
        entre sí (y mover la cabeza o la cola si era un extremo). En una lista
        simple habría que recorrerla para encontrar el nodo anterior: O(n).
        Complejidad: O(1).

        Returns:
            True si estaba en esta lista y se quitó; False si no pertenece a esta
            lista, ya se había quitado o es de antes de un ``vaciar()``
            (llamarlo dos veces es seguro).
        """
        if nodo is None or nodo._lista is not self or nodo._generacion != self._generacion:
            return False
        self._desenlazar(nodo)
        return True

    def vaciar(self) -> None:
        """Quita todos los elementos.

        Complejidad: O(1); el recolector libera los nodos. Los nodos viejos
        quedan invalidados al cambiar la generación.
        """
        self._cabeza = None
        self._cola = None
        self._tamanio = 0
        self._generacion += 1

    def conservar_ultimos(self, n: int) -> None:
        """Descarta los más antiguos (los del inicio) hasta que queden como máximo ``n``.

        Sirve para mantener una ventana deslizante de velas.
        Complejidad: O(k), con k elementos descartados (cada uno en O(1)).

        Raises:
            ValueError: si ``n`` es negativo.
        """
        if n < 0:
            raise ValueError(f"n no puede ser negativo: {n}")
        while self._tamanio > n:
            self.eliminar_primero()

    # ---------- recorrer ----------

    def iterador_adelante(self) -> Iterator[T]:
        """Iterador de la cabeza a la cola.

        Complejidad: O(1) crearlo y cada paso; O(n) el recorrido completo.
        """
        return _IteradorAdelante(self._cabeza)

    def iterador_atras(self) -> Iterator[T]:
        """Iterador de la cola a la cabeza, siguiendo los enlaces "anterior".

        Útil para leer primero los datos más recientes.
        Complejidad: O(1) crearlo y cada paso; O(n) el recorrido completo.
        """
        return _IteradorAtras(self._cola)

    def __iter__(self) -> Iterator[T]:
        """Igual que ``iterador_adelante()`` (para usar ``for``). Complejidad: O(1) por paso."""
        return self.iterador_adelante()

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar, por ejemplo ``ListaDoble(1, 2, 3)``. Complejidad: O(n)."""
        return "ListaDoble(" + ", ".join(repr(valor) for valor in self) + ")"

    # ---------- internos ----------

    def _nodo_en(self, indice: int) -> NodoDoble[T]:
        """Nodo de una posición ya validada, desde el extremo más cercano.

        Si está en la primera mitad avanza desde la cabeza; si no, retrocede
        desde la cola. Complejidad: O(min(i, n - i)).
        """
        if indice < self._tamanio // 2:
            actual = self._cabeza
            for _ in range(indice):
                assert actual is not None
                actual = actual._siguiente
        else:
            actual = self._cola
            for _ in range(self._tamanio - 1 - indice):
                assert actual is not None
                actual = actual._anterior
        assert actual is not None
        return actual

    def _desenlazar(self, nodo: NodoDoble[T]) -> T:
        """Saca un nodo uniendo a su anterior con su siguiente.

        Complejidad: O(1), porque el nodo ya conoce a sus dos vecinos.
        """
        anterior = nodo._anterior
        siguiente = nodo._siguiente
        if anterior is None:
            self._cabeza = siguiente
        else:
            anterior._siguiente = siguiente
        if siguiente is None:
            self._cola = anterior
        else:
            siguiente._anterior = anterior
        nodo._anterior = None
        nodo._siguiente = None
        nodo._lista = None
        self._tamanio -= 1
        return nodo._valor

    def _crear_nodo(self, valor: T) -> NodoDoble[T]:
        """Crea un nodo marcado como perteneciente a esta lista. O(1)."""
        nodo = NodoDoble(valor)
        nodo._lista = self
        nodo._generacion = self._generacion
        return nodo

    def _validar_indice(self, indice: int) -> None:
        if not 0 <= indice < self._tamanio:
            raise IndiceFueraDeRangoError(indice, self._tamanio)


class _IteradorAdelante[T]:
    """Iterador propio de la cabeza a la cola. Cada paso cuesta O(1)."""

    __slots__ = ("_actual",)

    def __init__(self, inicio: NodoDoble[T] | None) -> None:
        self._actual = inicio

    def __iter__(self) -> _IteradorAdelante[T]:
        return self

    def __next__(self) -> T:
        if self._actual is None:
            raise StopIteration
        valor = self._actual._valor
        self._actual = self._actual._siguiente
        return valor


class _IteradorAtras[T]:
    """Iterador propio de la cola a la cabeza. Cada paso cuesta O(1)."""

    __slots__ = ("_actual",)

    def __init__(self, inicio: NodoDoble[T] | None) -> None:
        self._actual = inicio

    def __iter__(self) -> _IteradorAtras[T]:
        return self

    def __next__(self) -> T:
        if self._actual is None:
            raise StopIteration
        valor = self._actual._valor
        self._actual = self._actual._anterior
        return valor
