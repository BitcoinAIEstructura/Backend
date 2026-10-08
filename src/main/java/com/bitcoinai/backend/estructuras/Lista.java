package com.bitcoinai.backend.estructuras;

import java.util.Comparator;
import java.util.Iterator;
import java.util.NoSuchElementException;
import java.util.Objects;
import java.util.function.Predicate;

/**
 * Lista simplemente enlazada genérica.
 *
 * <p>Guarda referencias a la cabeza y a la cola, así que agregar al inicio y al
 * final cuesta O(1). El acceso por índice recorre desde la cabeza y cuesta O(n).
 * En el proyecto se usa para registrar las operaciones cerradas.
 *
 * @param <T> tipo de los elementos
 */
public class Lista<T> implements Iterable<T> {

    private NodoSimple<T> cabeza;
    private NodoSimple<T> cola;
    private int tamanio;

    /**
     * Agrega un elemento al final.
     * Complejidad: O(1), gracias a la referencia a la cola.
     *
     * @param valor elemento a agregar
     */
    public void agregar(T valor) {
        NodoSimple<T> nuevo = new NodoSimple<>(valor);
        if (cola == null) {
            cabeza = nuevo;
        } else {
            cola.setSiguiente(nuevo);
        }
        cola = nuevo;
        tamanio++;
    }

    /**
     * Agrega un elemento al inicio.
     * Complejidad: O(1).
     *
     * @param valor elemento a agregar
     */
    public void agregarInicio(T valor) {
        cabeza = new NodoSimple<>(valor, cabeza);
        if (cola == null) {
            cola = cabeza;
        }
        tamanio++;
    }

    /**
     * Inserta un elemento manteniendo el orden dado por el comparador. Si hay
     * elementos iguales, el nuevo queda después de ellos (inserción estable).
     * Supone que la lista ya está ordenada con el mismo comparador.
     * Complejidad: O(n), porque puede recorrer toda la lista para hallar la posición.
     *
     * @param valor      elemento a insertar
     * @param comparador criterio de orden
     */
    public void insertarOrdenado(T valor, Comparator<T> comparador) {
        Objects.requireNonNull(comparador, "comparador");
        if (cabeza == null || comparador.compare(valor, cabeza.getValor()) < 0) {
            agregarInicio(valor);
            return;
        }
        NodoSimple<T> actual = cabeza;
        while (actual.getSiguiente() != null
                && comparador.compare(actual.getSiguiente().getValor(), valor) <= 0) {
            actual = actual.getSiguiente();
        }
        NodoSimple<T> nuevo = new NodoSimple<>(valor, actual.getSiguiente());
        actual.setSiguiente(nuevo);
        if (actual == cola) {
            cola = nuevo;
        }
        tamanio++;
    }

    /**
     * Devuelve el elemento en la posición indicada.
     * Complejidad: O(n) en general; O(1) para el primero y el último.
     *
     * @param indice posición entre 0 y tamanio() - 1
     * @return el elemento en esa posición
     * @throws IndiceFueraDeRangoException si el índice no existe
     */
    public T obtener(int indice) {
        validarIndice(indice);
        return nodoEn(indice).getValor();
    }

    /**
     * Elimina el elemento en la posición indicada y lo devuelve.
     * Complejidad: O(n), porque hay que llegar al nodo anterior; O(1) para el primero.
     *
     * @param indice posición entre 0 y tamanio() - 1
     * @return el elemento eliminado
     * @throws IndiceFueraDeRangoException si el índice no existe
     */
    public T eliminar(int indice) {
        validarIndice(indice);
        T valor;
        if (indice == 0) {
            valor = cabeza.getValor();
            cabeza = cabeza.getSiguiente();
            if (cabeza == null) {
                cola = null;
            }
        } else {
            NodoSimple<T> anterior = nodoEn(indice - 1);
            NodoSimple<T> eliminado = anterior.getSiguiente();
            valor = eliminado.getValor();
            anterior.setSiguiente(eliminado.getSiguiente());
            if (eliminado == cola) {
                cola = anterior;
            }
        }
        tamanio--;
        return valor;
    }

    /**
     * Busca el primer elemento que cumple la condición.
     * Complejidad: O(n).
     *
     * @param condicion criterio de búsqueda
     * @return el índice del primer elemento que la cumple, o -1 si ninguno
     */
    public int buscar(Predicate<T> condicion) {
        Objects.requireNonNull(condicion, "condicion");
        int indice = 0;
        for (NodoSimple<T> actual = cabeza; actual != null; actual = actual.getSiguiente()) {
            if (condicion.test(actual.getValor())) {
                return indice;
            }
            indice++;
        }
        return -1;
    }

    /**
     * Devuelve el primer elemento sin quitarlo.
     * Complejidad: O(1).
     *
     * @return el primer elemento
     * @throws EstructuraVaciaException si la lista está vacía
     */
    public T primero() {
        if (cabeza == null) {
            throw new EstructuraVaciaException("La lista está vacía");
        }
        return cabeza.getValor();
    }

    /**
     * Devuelve el último elemento sin quitarlo.
     * Complejidad: O(1), gracias a la referencia a la cola.
     *
     * @return el último elemento
     * @throws EstructuraVaciaException si la lista está vacía
     */
    public T ultimo() {
        if (cola == null) {
            throw new EstructuraVaciaException("La lista está vacía");
        }
        return cola.getValor();
    }

    /**
     * Devuelve la cantidad de elementos.
     * Complejidad: O(1), porque se lleva un contador.
     *
     * @return el tamaño de la lista
     */
    public int tamanio() {
        return tamanio;
    }

    /**
     * Indica si la lista no tiene elementos.
     * Complejidad: O(1).
     *
     * @return true si está vacía
     */
    public boolean estaVacia() {
        return tamanio == 0;
    }

    /**
     * Quita todos los elementos.
     * Complejidad: O(1); el recolector de basura libera los nodos.
     */
    public void vaciar() {
        cabeza = null;
        cola = null;
        tamanio = 0;
    }

    /**
     * Devuelve un iterador que recorre de la cabeza a la cola, para usar for-each.
     * Complejidad: O(1) crearlo; O(n) recorrer toda la lista.
     *
     * @return iterador hacia adelante
     */
    @Override
    public Iterator<T> iterator() {
        return new IteradorLista();
    }

    /** Recorre hasta el nodo en la posición dada (ya validada). O(n), O(1) para el último. */
    private NodoSimple<T> nodoEn(int indice) {
        if (indice == tamanio - 1) {
            return cola;
        }
        NodoSimple<T> actual = cabeza;
        for (int i = 0; i < indice; i++) {
            actual = actual.getSiguiente();
        }
        return actual;
    }

    private void validarIndice(int indice) {
        if (indice < 0 || indice >= tamanio) {
            throw new IndiceFueraDeRangoException(indice, tamanio);
        }
    }

    /** Iterador propio que avanza nodo a nodo. Cada paso cuesta O(1). */
    private class IteradorLista implements Iterator<T> {

        private NodoSimple<T> actual = cabeza;

        @Override
        public boolean hasNext() {
            return actual != null;
        }

        @Override
        public T next() {
            if (actual == null) {
                throw new NoSuchElementException("No hay más elementos");
            }
            T valor = actual.getValor();
            actual = actual.getSiguiente();
            return valor;
        }
    }
}
