package com.bitcoinai.backend.util;

/**
 * Se lanza cuando un texto no es JSON válido. Indica la posición (índice del
 * carácter, empezando en 0) donde se detectó el problema.
 */
public class JsonException extends RuntimeException {

    private final int posicion;

    /**
     * Crea la excepción.
     *
     * @param mensaje  descripción del problema
     * @param posicion índice del carácter donde se detectó
     */
    public JsonException(String mensaje, int posicion) {
        super(mensaje + " (posición " + posicion + ")");
        this.posicion = posicion;
    }

    /**
     * Devuelve la posición del error.
     *
     * @return índice del carácter, empezando en 0
     */
    public int getPosicion() {
        return posicion;
    }
}
