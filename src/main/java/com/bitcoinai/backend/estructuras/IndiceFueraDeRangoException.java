package com.bitcoinai.backend.estructuras;

/**
 * Se lanza cuando se usa un índice que no existe en la estructura.
 */
public class IndiceFueraDeRangoException extends RuntimeException {

    /**
     * Crea la excepción indicando el índice pedido y el tamaño actual.
     * Complejidad: O(1).
     *
     * @param indice  índice que se intentó usar
     * @param tamanio tamaño de la estructura en ese momento
     */
    public IndiceFueraDeRangoException(int indice, int tamanio) {
        super("Índice " + indice + " fuera de rango para tamaño " + tamanio);
    }
}
