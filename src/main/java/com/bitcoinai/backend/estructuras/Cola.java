package com.bitcoinai.backend.estructuras;

/**
 * Cola genérica FIFO (el primero en entrar es el primero en salir), con nodos
 * simples y referencias al frente y al final.
 *
 * <p>Se encola por el final y se desencola por el frente, así que todas las
 * operaciones cuestan O(1). En el proyecto guarda las órdenes pendientes.
 *
 * @param <T> tipo de los elementos
 */
public class Cola<T> {

    private NodoSimple<T> frente;
    private NodoSimple<T> fin;
    private int tamanio;

    /**
     * Agrega un elemento al final de la cola.
     * Complejidad: O(1), gracias a la referencia al final.
     *
     * @param valor elemento a encolar
     */
    public void encolar(T valor) {
        NodoSimple<T> nuevo = new NodoSimple<>(valor);
        if (fin == null) {
            frente = nuevo;
        } else {
            fin.setSiguiente(nuevo);
        }
        fin = nuevo;
        tamanio++;
    }

    /**
     * Quita y devuelve el elemento del frente.
     * Complejidad: O(1).
     *
     * @return el elemento más antiguo de la cola
     * @throws EstructuraVaciaException si la cola está vacía
     */
    public T desencolar() {
        if (frente == null) {
            throw new EstructuraVaciaException("La cola está vacía");
        }
        T valor = frente.getValor();
        frente = frente.getSiguiente();
        if (frente == null) {
            fin = null;
        }
        tamanio--;
        return valor;
    }

    /**
     * Devuelve el elemento del frente sin quitarlo.
     * Complejidad: O(1).
     *
     * @return el elemento más antiguo de la cola
     * @throws EstructuraVaciaException si la cola está vacía
     */
    public T verFrente() {
        if (frente == null) {
            throw new EstructuraVaciaException("La cola está vacía");
        }
        return frente.getValor();
    }

    /**
     * Devuelve la cantidad de elementos.
     * Complejidad: O(1), porque se lleva un contador.
     *
     * @return el tamaño de la cola
     */
    public int tamanio() {
        return tamanio;
    }

    /**
     * Indica si la cola no tiene elementos.
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
        frente = null;
        fin = null;
        tamanio = 0;
    }
}
