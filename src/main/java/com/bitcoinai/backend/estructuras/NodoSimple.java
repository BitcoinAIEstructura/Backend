package com.bitcoinai.backend.estructuras;

/**
 * Nodo de una estructura simplemente enlazada: guarda un valor y la referencia
 * al nodo siguiente. Lo usan {@link Lista}, {@link Cola} y {@link Pila}.
 *
 * <p>Los modificadores son de paquete para que solo las estructuras puedan
 * reenlazar nodos y no se rompa su consistencia desde fuera.
 *
 * @param <T> tipo del valor almacenado
 */
public class NodoSimple<T> {

    private final T valor;
    private NodoSimple<T> siguiente;

    /**
     * Crea un nodo sin siguiente.
     * Complejidad: O(1).
     *
     * @param valor valor a guardar
     */
    public NodoSimple(T valor) {
        this(valor, null);
    }

    /**
     * Crea un nodo enlazado a otro.
     * Complejidad: O(1).
     *
     * @param valor     valor a guardar
     * @param siguiente nodo que sigue a este, o null
     */
    public NodoSimple(T valor, NodoSimple<T> siguiente) {
        this.valor = valor;
        this.siguiente = siguiente;
    }

    /**
     * Devuelve el valor guardado.
     * Complejidad: O(1).
     *
     * @return el valor del nodo
     */
    public T getValor() {
        return valor;
    }

    /**
     * Devuelve el nodo siguiente.
     * Complejidad: O(1).
     *
     * @return el siguiente nodo, o null si es el último
     */
    public NodoSimple<T> getSiguiente() {
        return siguiente;
    }

    /** Cambia el nodo siguiente. Complejidad: O(1). */
    void setSiguiente(NodoSimple<T> siguiente) {
        this.siguiente = siguiente;
    }
}
