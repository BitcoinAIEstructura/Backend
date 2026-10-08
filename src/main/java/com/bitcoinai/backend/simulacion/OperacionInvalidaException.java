package com.bitcoinai.backend.simulacion;

/**
 * La operación no se puede hacer en el estado actual (por ejemplo, cancelar una
 * orden ya ejecutada, o procesar con la cola vacía).
 */
public class OperacionInvalidaException extends RuntimeException {

    /**
     * Crea la excepción.
     *
     * @param mensaje explicación en español
     */
    public OperacionInvalidaException(String mensaje) {
        super(mensaje);
    }
}
