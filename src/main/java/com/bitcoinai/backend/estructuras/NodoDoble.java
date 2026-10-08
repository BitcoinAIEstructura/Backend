package com.bitcoinai.backend.estructuras;

/**
 * Nodo de una estructura doblemente enlazada: guarda un valor y las referencias
 * al nodo anterior y al siguiente. Lo usa {@link ListaDoble}.
 *
 * <p>Los modificadores son de paquete para que solo las estructuras puedan
 * reenlazar nodos y no se rompa su consistencia desde fuera.
 *
 * @param <T> tipo del valor almacenado
 */
public class NodoDoble<T> {

    private final T valor;
    private NodoDoble<T> anterior;
    private NodoDoble<T> siguiente;

    /**
     * Lista a la que pertenece y su "generación" en ese momento (cambia con
     * vaciar()). Permiten que {@link ListaDoble#eliminarNodo} compruebe en O(1)
     * que el nodo sigue en esa lista. Los maneja solo ListaDoble.
     */
    Object lista;
    long generacion;

    /**
     * Crea un nodo sin enlaces.
     * Complejidad: O(1).
     *
     * @param valor valor a guardar
     */
    public NodoDoble(T valor) {
        this.valor = valor;
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
     * Devuelve el nodo anterior.
     * Complejidad: O(1).
     *
     * @return el nodo anterior, o null si es el primero
     */
    public NodoDoble<T> getAnterior() {
        return anterior;
    }

    /**
     * Devuelve el nodo siguiente.
     * Complejidad: O(1).
     *
     * @return el nodo siguiente, o null si es el último
     */
    public NodoDoble<T> getSiguiente() {
        return siguiente;
    }

    /** Cambia el nodo anterior. Complejidad: O(1). */
    void setAnterior(NodoDoble<T> anterior) {
        this.anterior = anterior;
    }

    /** Cambia el nodo siguiente. Complejidad: O(1). */
    void setSiguiente(NodoDoble<T> siguiente) {
        this.siguiente = siguiente;
    }
}
