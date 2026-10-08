package com.bitcoinai.backend.estructuras;

/**
 * Se lanza al intentar leer o quitar un elemento de una estructura vacía
 * (desencolar, desapilar, eliminarPrimero, primero, etc.).
 */
public class EstructuraVaciaException extends RuntimeException {

    /**
     * Crea la excepción con un mensaje.
     * Complejidad: O(1).
     *
     * @param mensaje descripción de la operación que falló
     */
    public EstructuraVaciaException(String mensaje) {
        super(mensaje);
    }
}
