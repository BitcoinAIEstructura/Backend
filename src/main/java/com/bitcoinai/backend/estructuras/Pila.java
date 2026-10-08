package com.bitcoinai.backend.estructuras;

/**
 * Pila genérica LIFO (el último en entrar es el primero en salir), con nodos
 * simples y una referencia al tope.
 *
 * <p>Se apila y se desapila siempre por el tope, así que todas las operaciones
 * cuestan O(1). En el proyecto guarda el historial de decisiones, con la más
 * reciente arriba.
 *
 * @param <T> tipo de los elementos
 */
public class Pila<T> {

    private NodoSimple<T> tope;
    private int tamanio;

    /**
     * Pone un elemento en el tope.
     * Complejidad: O(1).
     *
     * @param valor elemento a apilar
     */
    public void apilar(T valor) {
        tope = new NodoSimple<>(valor, tope);
        tamanio++;
    }

    /**
     * Quita y devuelve el elemento del tope.
     * Complejidad: O(1).
     *
     * @return el último elemento apilado
     * @throws EstructuraVaciaException si la pila está vacía
     */
    public T desapilar() {
        if (tope == null) {
            throw new EstructuraVaciaException("La pila está vacía");
        }
        T valor = tope.getValor();
        tope = tope.getSiguiente();
        tamanio--;
        return valor;
    }

    /**
     * Devuelve el elemento del tope sin quitarlo.
     * Complejidad: O(1).
     *
     * @return el último elemento apilado
     * @throws EstructuraVaciaException si la pila está vacía
     */
    public T verTope() {
        if (tope == null) {
            throw new EstructuraVaciaException("La pila está vacía");
        }
        return tope.getValor();
    }

    /**
     * Devuelve la cantidad de elementos.
     * Complejidad: O(1), porque se lleva un contador.
     *
     * @return el tamaño de la pila
     */
    public int tamanio() {
        return tamanio;
    }

    /**
     * Indica si la pila no tiene elementos.
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
        tope = null;
        tamanio = 0;
    }
}
