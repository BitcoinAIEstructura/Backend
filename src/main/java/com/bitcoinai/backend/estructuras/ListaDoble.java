package com.bitcoinai.backend.estructuras;

import java.util.Iterator;
import java.util.NoSuchElementException;

/**
 * Lista doblemente enlazada genérica con referencias a la cabeza y a la cola.
 *
 * <p>Cada nodo conoce a su anterior y a su siguiente, así que se puede agregar y
 * quitar en ambos extremos en O(1), recorrer en los dos sentidos y llegar a un
 * índice desde el extremo más cercano. En el proyecto guarda la ventana de velas:
 * las nuevas entran por el final y las más antiguas salen por el inicio con
 * {@link #conservarUltimos(int)}.
 *
 * @param <T> tipo de los elementos
 */
public class ListaDoble<T> implements Iterable<T> {

    private NodoDoble<T> cabeza;
    private NodoDoble<T> cola;
    private int tamanio;
    /** Aumenta en cada vaciar(), para invalidar en O(1) los nodos que había antes. */
    private long generacion;

    /**
     * Agrega un elemento al inicio.
     * Complejidad: O(1).
     *
     * @param valor elemento a agregar
     */
    public void agregarInicio(T valor) {
        NodoDoble<T> nuevo = crearNodo(valor);
        if (cabeza == null) {
            cola = nuevo;
        } else {
            nuevo.setSiguiente(cabeza);
            cabeza.setAnterior(nuevo);
        }
        cabeza = nuevo;
        tamanio++;
    }

    /**
     * Agrega un elemento al final.
     * Complejidad: O(1).
     *
     * @param valor elemento a agregar
     */
    public void agregarFinal(T valor) {
        agregarFinalNodo(valor);
    }

    /**
     * Agrega un elemento al final y devuelve su nodo, para poder quitarlo después
     * en O(1) con {@link #eliminarNodo(NodoDoble)} sin buscarlo.
     * Complejidad: O(1).
     *
     * @param valor elemento a agregar
     * @return el nodo que lo contiene
     */
    public NodoDoble<T> agregarFinalNodo(T valor) {
        NodoDoble<T> nuevo = crearNodo(valor);
        if (cola == null) {
            cabeza = nuevo;
        } else {
            nuevo.setAnterior(cola);
            cola.setSiguiente(nuevo);
        }
        cola = nuevo;
        tamanio++;
        return nuevo;
    }

    /**
     * Quita un nodo de la lista sin recorrerla.
     *
     * <p>Como el nodo conoce a su anterior y a su siguiente, basta con unirlos
     * entre sí (y mover la cabeza o la cola si era un extremo). En una lista
     * simple habría que recorrerla para encontrar el nodo anterior: O(n).
     * Complejidad: O(1).
     *
     * @param nodo nodo devuelto por {@link #agregarFinalNodo(Object)}
     * @return true si estaba en esta lista y se quitó; false si no pertenece a
     *         esta lista o ya se había quitado (llamarlo dos veces es seguro)
     */
    public boolean eliminarNodo(NodoDoble<T> nodo) {
        if (nodo == null || nodo.lista != this || nodo.generacion != generacion) {
            return false;
        }
        desenlazar(nodo);
        return true;
    }

    /**
     * Inserta un elemento en la posición indicada; los que estaban desde esa
     * posición se corren una a la derecha. Con índice igual a tamanio() agrega al final.
     * Complejidad: O(min(i, n - i)), porque llega a la posición desde el extremo más cercano.
     *
     * @param indice posición entre 0 y tamanio()
     * @param valor  elemento a insertar
     * @throws IndiceFueraDeRangoException si el índice no está en ese rango
     */
    public void insertar(int indice, T valor) {
        if (indice < 0 || indice > tamanio) {
            throw new IndiceFueraDeRangoException(indice, tamanio);
        }
        if (indice == 0) {
            agregarInicio(valor);
        } else if (indice == tamanio) {
            agregarFinal(valor);
        } else {
            NodoDoble<T> siguiente = nodoEn(indice);
            NodoDoble<T> anterior = siguiente.getAnterior();
            NodoDoble<T> nuevo = crearNodo(valor);
            nuevo.setAnterior(anterior);
            nuevo.setSiguiente(siguiente);
            anterior.setSiguiente(nuevo);
            siguiente.setAnterior(nuevo);
            tamanio++;
        }
    }

    /**
     * Devuelve el elemento en la posición indicada, recorriendo desde la cabeza o
     * desde la cola según cuál esté más cerca.
     * Complejidad: O(min(i, n - i)); en el peor caso O(n/2).
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
     * Quita y devuelve el primer elemento.
     * Complejidad: O(1).
     *
     * @return el elemento que estaba al inicio
     * @throws EstructuraVaciaException si la lista está vacía
     */
    public T eliminarPrimero() {
        if (cabeza == null) {
            throw new EstructuraVaciaException("La lista doble está vacía");
        }
        return desenlazar(cabeza);
    }

    /**
     * Quita y devuelve el último elemento.
     * Complejidad: O(1), porque la cola conoce a su anterior.
     *
     * @return el elemento que estaba al final
     * @throws EstructuraVaciaException si la lista está vacía
     */
    public T eliminarUltimo() {
        if (cola == null) {
            throw new EstructuraVaciaException("La lista doble está vacía");
        }
        return desenlazar(cola);
    }

    /**
     * Quita y devuelve el elemento en la posición indicada.
     * Complejidad: O(min(i, n - i)) para llegar al nodo; desenlazarlo es O(1).
     *
     * @param indice posición entre 0 y tamanio() - 1
     * @return el elemento eliminado
     * @throws IndiceFueraDeRangoException si el índice no existe
     */
    public T eliminar(int indice) {
        validarIndice(indice);
        return desenlazar(nodoEn(indice));
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
            throw new EstructuraVaciaException("La lista doble está vacía");
        }
        return cabeza.getValor();
    }

    /**
     * Devuelve el último elemento sin quitarlo.
     * Complejidad: O(1).
     *
     * @return el último elemento
     * @throws EstructuraVaciaException si la lista está vacía
     */
    public T ultimo() {
        if (cola == null) {
            throw new EstructuraVaciaException("La lista doble está vacía");
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
     * Complejidad: O(1); el recolector de basura libera los nodos. Los nodos
     * viejos quedan invalidados al cambiar la generación.
     */
    public void vaciar() {
        cabeza = null;
        cola = null;
        tamanio = 0;
        generacion++;
    }

    /**
     * Descarta los elementos más antiguos (los del inicio) hasta que queden como
     * máximo n. Sirve para mantener una ventana deslizante de velas.
     * Complejidad: O(k), donde k es la cantidad de elementos descartados; cada
     * descarte es un eliminarPrimero() en O(1).
     *
     * @param n tamaño máximo de la ventana (0 o más)
     * @throws IllegalArgumentException si n es negativo
     */
    public void conservarUltimos(int n) {
        if (n < 0) {
            throw new IllegalArgumentException("n no puede ser negativo: " + n);
        }
        while (tamanio > n) {
            eliminarPrimero();
        }
    }

    /**
     * Devuelve un iterador que recorre de la cabeza a la cola.
     * Complejidad: O(1) crearlo; O(n) recorrer toda la lista.
     *
     * @return iterador hacia adelante
     */
    public Iterator<T> iteradorAdelante() {
        return new IteradorAdelante();
    }

    /**
     * Devuelve un iterador que recorre de la cola a la cabeza, siguiendo los
     * enlaces "anterior". Útil para leer primero los datos más recientes.
     * Complejidad: O(1) crearlo; O(n) recorrer toda la lista.
     *
     * @return iterador hacia atrás
     */
    public Iterator<T> iteradorAtras() {
        return new IteradorAtras();
    }

    /**
     * Devuelve el iterador hacia adelante, para usar for-each.
     * Complejidad: O(1) crearlo; O(n) recorrer toda la lista.
     *
     * @return iterador hacia adelante
     */
    @Override
    public Iterator<T> iterator() {
        return iteradorAdelante();
    }

    /**
     * Llega al nodo de la posición dada (ya validada) desde el extremo más cercano.
     * Si está en la primera mitad avanza desde la cabeza; si no, retrocede desde la cola.
     * Complejidad: O(min(i, n - i)).
     */
    private NodoDoble<T> nodoEn(int indice) {
        NodoDoble<T> actual;
        if (indice < tamanio / 2) {
            actual = cabeza;
            for (int i = 0; i < indice; i++) {
                actual = actual.getSiguiente();
            }
        } else {
            actual = cola;
            for (int i = tamanio - 1; i > indice; i--) {
                actual = actual.getAnterior();
            }
        }
        return actual;
    }

    /**
     * Saca un nodo de la lista uniendo a su anterior con su siguiente.
     * Complejidad: O(1), porque el nodo ya conoce a sus dos vecinos.
     */
    private T desenlazar(NodoDoble<T> nodo) {
        NodoDoble<T> anterior = nodo.getAnterior();
        NodoDoble<T> siguiente = nodo.getSiguiente();
        if (anterior == null) {
            cabeza = siguiente;
        } else {
            anterior.setSiguiente(siguiente);
        }
        if (siguiente == null) {
            cola = anterior;
        } else {
            siguiente.setAnterior(anterior);
        }
        nodo.setAnterior(null);
        nodo.setSiguiente(null);
        nodo.lista = null;
        tamanio--;
        return nodo.getValor();
    }

    /** Crea un nodo marcado como perteneciente a esta lista. O(1). */
    private NodoDoble<T> crearNodo(T valor) {
        NodoDoble<T> nodo = new NodoDoble<>(valor);
        nodo.lista = this;
        nodo.generacion = generacion;
        return nodo;
    }

    private void validarIndice(int indice) {
        if (indice < 0 || indice >= tamanio) {
            throw new IndiceFueraDeRangoException(indice, tamanio);
        }
    }

    /** Iterador propio de la cabeza a la cola. Cada paso cuesta O(1). */
    private class IteradorAdelante implements Iterator<T> {

        private NodoDoble<T> actual = cabeza;

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

    /** Iterador propio de la cola a la cabeza. Cada paso cuesta O(1). */
    private class IteradorAtras implements Iterator<T> {

        private NodoDoble<T> actual = cola;

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
            actual = actual.getAnterior();
            return valor;
        }
    }
}
