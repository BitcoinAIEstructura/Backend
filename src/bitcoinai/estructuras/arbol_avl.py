"""Árbol AVL: árbol binario de búsqueda que se mantiene balanceado."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from bitcoinai.estructuras.excepciones import EstructuraVaciaError
from bitcoinai.estructuras.lista import Lista

if TYPE_CHECKING:
    from _typeshed import SupportsDunderLT


class NodoAVL[K, V]:
    """Un nodo del árbol: clave, valor, hijos y la altura de su subárbol.

    Desde afuera solo se lee (para dibujar el árbol); lo cambia el ``ArbolAVL``.
    """

    __slots__ = ("_altura", "_clave", "_derecho", "_izquierdo", "_valor")

    def __init__(self, clave: K, valor: V) -> None:
        """Crea una hoja. Complejidad: O(1)."""
        self._clave = clave
        self._valor = valor
        self._izquierdo: NodoAVL[K, V] | None = None
        self._derecho: NodoAVL[K, V] | None = None
        self._altura = 1

    @property
    def clave(self) -> K:
        return self._clave

    @property
    def valor(self) -> V:
        return self._valor

    @property
    def izquierdo(self) -> NodoAVL[K, V] | None:
        return self._izquierdo

    @property
    def derecho(self) -> NodoAVL[K, V] | None:
        return self._derecho

    @property
    def altura(self) -> int:
        return self._altura


def _altura(nodo: NodoAVL[Any, Any] | None) -> int:
    return 0 if nodo is None else nodo._altura


def _actualizar(nodo: NodoAVL[Any, Any]) -> None:
    nodo._altura = 1 + max(_altura(nodo._izquierdo), _altura(nodo._derecho))


def _balance(nodo: NodoAVL[Any, Any]) -> int:
    """Altura izquierda menos altura derecha: en un AVL siempre está entre -1 y 1."""
    return _altura(nodo._izquierdo) - _altura(nodo._derecho)


class ArbolAVL[K: SupportsDunderLT[Any], V]:
    """Mapa ordenado ``clave → valor`` con búsqueda, inserción y borrado en O(log n).

    Es un árbol binario de búsqueda (a la izquierda las claves menores, a la
    derecha las mayores) que después de cada cambio revisa el balance de los nodos
    del camino. Si un lado quedó dos niveles más alto que el otro, lo corrige con
    rotaciones (simple o doble). Así la altura nunca pasa de ~1,44·log₂(n) y no
    degenera en una lista, aunque las claves lleguen ya ordenadas (como las velas).

    Además de buscar una clave exacta responde "la primera clave mayor o igual"
    (``techo``) y "la última menor o igual" (``piso``), y recorre un rango en orden.

    En el proyecto indexa las velas por su hora de apertura para "¿y si hubiera
    invertido?": encuentra la vela de cualquier fecha en O(log n).
    """

    __slots__ = ("_raiz", "_rotaciones", "_tamanio")

    def __init__(self) -> None:
        """Crea un árbol vacío. Complejidad: O(1)."""
        self._raiz: NodoAVL[K, V] | None = None
        self._tamanio = 0
        self._rotaciones: Lista[str] = Lista()

    # ---------- rotaciones ----------

    def _rotar_derecha(self, y: NodoAVL[K, V]) -> NodoAVL[K, V]:
        """El hijo izquierdo sube y ``y`` baja a su derecha. Complejidad: O(1)."""
        x = y._izquierdo
        assert x is not None
        y._izquierdo = x._derecho
        x._derecho = y
        _actualizar(y)
        _actualizar(x)
        return x

    def _rotar_izquierda(self, x: NodoAVL[K, V]) -> NodoAVL[K, V]:
        """El hijo derecho sube y ``x`` baja a su izquierda. Complejidad: O(1)."""
        y = x._derecho
        assert y is not None
        x._derecho = y._izquierdo
        y._izquierdo = x
        _actualizar(x)
        _actualizar(y)
        return y

    def _rebalancear(self, nodo: NodoAVL[K, V]) -> NodoAVL[K, V]:
        """Corrige el nodo si quedó desbalanceado y devuelve la nueva raíz del subárbol.

        Los cuatro casos: izquierda-izquierda y derecha-derecha con una rotación
        simple; izquierda-derecha y derecha-izquierda con una doble. Complejidad: O(1).
        """
        _actualizar(nodo)
        balance = _balance(nodo)
        if balance > 1:
            assert nodo._izquierdo is not None
            if _balance(nodo._izquierdo) < 0:
                self._rotaciones.agregar(f"Rotación doble izquierda-derecha en {nodo._clave}")
                nodo._izquierdo = self._rotar_izquierda(nodo._izquierdo)
            else:
                self._rotaciones.agregar(f"Rotación simple a la derecha en {nodo._clave}")
            return self._rotar_derecha(nodo)
        if balance < -1:
            assert nodo._derecho is not None
            if _balance(nodo._derecho) > 0:
                self._rotaciones.agregar(f"Rotación doble derecha-izquierda en {nodo._clave}")
                nodo._derecho = self._rotar_derecha(nodo._derecho)
            else:
                self._rotaciones.agregar(f"Rotación simple a la izquierda en {nodo._clave}")
            return self._rotar_izquierda(nodo)
        return nodo

    # ---------- insertar y eliminar ----------

    def insertar(self, clave: K, valor: V) -> bool:
        """Guarda ``valor`` en ``clave``; si la clave ya estaba, cambia su valor.

        Complejidad: O(log n).

        Returns:
            True si la clave era nueva; False si solo se cambió el valor.
        """
        self._rotaciones = Lista()
        tamanio_antes = self._tamanio
        self._raiz = self._insertar(self._raiz, clave, valor)
        return self._tamanio > tamanio_antes

    def _insertar(self, nodo: NodoAVL[K, V] | None, clave: K, valor: V) -> NodoAVL[K, V]:
        if nodo is None:
            self._tamanio += 1
            return NodoAVL(clave, valor)
        if clave < nodo._clave:
            nodo._izquierdo = self._insertar(nodo._izquierdo, clave, valor)
        elif nodo._clave < clave:
            nodo._derecho = self._insertar(nodo._derecho, clave, valor)
        else:
            nodo._valor = valor
            return nodo
        return self._rebalancear(nodo)

    def eliminar(self, clave: K) -> bool:
        """Quita la clave. Con dos hijos, la reemplaza su sucesor (la menor de la derecha).

        Complejidad: O(log n).

        Returns:
            True si estaba; False si no.
        """
        self._rotaciones = Lista()
        tamanio_antes = self._tamanio
        self._raiz = self._eliminar(self._raiz, clave)
        return self._tamanio < tamanio_antes

    def _eliminar(self, nodo: NodoAVL[K, V] | None, clave: K) -> NodoAVL[K, V] | None:
        if nodo is None:
            return None
        if clave < nodo._clave:
            nodo._izquierdo = self._eliminar(nodo._izquierdo, clave)
        elif nodo._clave < clave:
            nodo._derecho = self._eliminar(nodo._derecho, clave)
        else:
            if nodo._izquierdo is None or nodo._derecho is None:
                self._tamanio -= 1
                return nodo._izquierdo or nodo._derecho
            sucesor = nodo._derecho
            while sucesor._izquierdo is not None:
                sucesor = sucesor._izquierdo
            nodo._clave, nodo._valor = sucesor._clave, sucesor._valor
            nodo._derecho = self._eliminar(nodo._derecho, sucesor._clave)
        return self._rebalancear(nodo)

    # ---------- búsquedas ----------

    def buscar(self, clave: K) -> V | None:
        """Valor de la clave, o ``None`` si no está. Complejidad: O(log n)."""
        nodo = self._raiz
        while nodo is not None:
            if clave < nodo._clave:
                nodo = nodo._izquierdo
            elif nodo._clave < clave:
                nodo = nodo._derecho
            else:
                return nodo._valor
        return None

    def contiene(self, clave: K) -> bool:
        """Indica si la clave está. Complejidad: O(log n)."""
        nodo = self._raiz
        while nodo is not None:
            if clave < nodo._clave:
                nodo = nodo._izquierdo
            elif nodo._clave < clave:
                nodo = nodo._derecho
            else:
                return True
        return False

    def techo(self, clave: K) -> tuple[K, V] | None:
        """La primera clave mayor o igual a ``clave`` (con su valor), o ``None``.

        Baja por una sola rama recordando el mejor candidato. Complejidad: O(log n).
        """
        nodo, mejor = self._raiz, None
        while nodo is not None:
            if nodo._clave < clave:
                nodo = nodo._derecho
            else:
                mejor = nodo
                if not clave < nodo._clave:
                    break
                nodo = nodo._izquierdo
        return None if mejor is None else (mejor._clave, mejor._valor)

    def piso(self, clave: K) -> tuple[K, V] | None:
        """La última clave menor o igual a ``clave`` (con su valor), o ``None``. Complejidad: O(log n)."""
        nodo, mejor = self._raiz, None
        while nodo is not None:
            if clave < nodo._clave:
                nodo = nodo._izquierdo
            else:
                mejor = nodo
                if not nodo._clave < clave:
                    break
                nodo = nodo._derecho
        return None if mejor is None else (mejor._clave, mejor._valor)

    def minimo(self) -> tuple[K, V]:
        """La clave menor. Complejidad: O(log n).

        Raises:
            EstructuraVaciaError: si el árbol está vacío.
        """
        if self._raiz is None:
            raise EstructuraVaciaError("El árbol está vacío")
        nodo = self._raiz
        while nodo._izquierdo is not None:
            nodo = nodo._izquierdo
        return nodo._clave, nodo._valor

    def maximo(self) -> tuple[K, V]:
        """La clave mayor. Complejidad: O(log n).

        Raises:
            EstructuraVaciaError: si el árbol está vacío.
        """
        if self._raiz is None:
            raise EstructuraVaciaError("El árbol está vacío")
        nodo = self._raiz
        while nodo._derecho is not None:
            nodo = nodo._derecho
        return nodo._clave, nodo._valor

    def rango(self, desde: K, hasta: K) -> Lista[tuple[K, V]]:
        """Las claves entre ``desde`` y ``hasta`` (ambas incluidas), en orden.

        Solo entra a las ramas que pueden tener claves del rango.
        Complejidad: O(log n + k), con k resultados.
        """
        resultado: Lista[tuple[K, V]] = Lista()
        self._rango(self._raiz, desde, hasta, resultado)
        return resultado

    def _rango(self, nodo: NodoAVL[K, V] | None, desde: K, hasta: K, resultado: Lista[tuple[K, V]]) -> None:
        if nodo is None:
            return
        if desde < nodo._clave:
            self._rango(nodo._izquierdo, desde, hasta, resultado)
        if not nodo._clave < desde and not hasta < nodo._clave:
            resultado.agregar((nodo._clave, nodo._valor))
        if nodo._clave < hasta:
            self._rango(nodo._derecho, desde, hasta, resultado)

    def en_orden(self) -> Iterator[tuple[K, V]]:
        """Todas las claves de menor a mayor (recorrido inorden). Complejidad: O(n)."""
        yield from self._en_orden(self._raiz)

    def _en_orden(self, nodo: NodoAVL[K, V] | None) -> Iterator[tuple[K, V]]:
        if nodo is not None:
            yield from self._en_orden(nodo._izquierdo)
            yield nodo._clave, nodo._valor
            yield from self._en_orden(nodo._derecho)

    # ---------- forma ----------

    def raiz(self) -> NodoAVL[K, V] | None:
        """La raíz, para dibujar el árbol (solo lectura). Complejidad: O(1)."""
        return self._raiz

    def altura(self) -> int:
        """Niveles del árbol (0 si está vacío). Complejidad: O(1)."""
        return _altura(self._raiz)

    def rotaciones_ultima_operacion(self) -> Lista[str]:
        """Las rotaciones que hizo la última inserción o eliminación, en orden. Complejidad: O(1)."""
        return self._rotaciones

    def tamanio(self) -> int:
        """Cantidad de claves. Complejidad: O(1)."""
        return self._tamanio

    def esta_vacio(self) -> bool:
        """Indica si no hay claves. Complejidad: O(1)."""
        return self._tamanio == 0

    def __len__(self) -> int:
        """Igual que ``tamanio()``. Complejidad: O(1)."""
        return self._tamanio

    def __repr__(self) -> str:
        """Representación para depurar, por ejemplo ``ArbolAVL(tamanio=3, altura=2)``. Complejidad: O(1)."""
        return f"ArbolAVL(tamanio={self._tamanio}, altura={self.altura()})"
