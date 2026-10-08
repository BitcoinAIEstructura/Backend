package com.bitcoinai.backend.mercado;

/**
 * Error al obtener o validar datos de mercado: la fuente no responde, responde
 * con un código de error, o entrega datos inválidos.
 */
public class MercadoException extends RuntimeException {

    /**
     * Crea la excepción con un mensaje.
     *
     * @param mensaje descripción clara del problema
     */
    public MercadoException(String mensaje) {
        super(mensaje);
    }

    /**
     * Crea la excepción con un mensaje y la causa original.
     *
     * @param mensaje descripción clara del problema
     * @param causa   excepción que lo provocó
     */
    public MercadoException(String mensaje, Throwable causa) {
        super(mensaje, causa);
    }
}
