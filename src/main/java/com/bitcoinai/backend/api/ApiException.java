package com.bitcoinai.backend.api;

/**
 * Error que se devuelve al cliente tal cual, con su código HTTP y un mensaje
 * pensado para él (por ejemplo, 400 con el motivo de un parámetro inválido).
 */
public class ApiException extends RuntimeException {

    private final int codigo;

    /**
     * Crea el error.
     *
     * @param codigo  código HTTP (4xx normalmente)
     * @param mensaje mensaje que verá el cliente en {"error": "..."}
     */
    public ApiException(int codigo, String mensaje) {
        super(mensaje);
        this.codigo = codigo;
    }

    /**
     * Devuelve el código HTTP.
     *
     * @return el código
     */
    public int getCodigo() {
        return codigo;
    }
}
