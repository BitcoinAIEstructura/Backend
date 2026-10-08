package com.bitcoinai.backend.simulacion;

/** La cartera no puede ejecutar una operación (por ejemplo, saldo insuficiente). */
public class OperacionRechazadaException extends RuntimeException {

    /**
     * Crea la excepción.
     *
     * @param razon razón en español, que queda como detalle de la orden rechazada
     */
    public OperacionRechazadaException(String razon) {
        super(razon);
    }
}
