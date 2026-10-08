package com.bitcoinai.backend.api;

/**
 * Respuesta de un manejador: código HTTP y cuerpo, que se escribe como JSON.
 *
 * @param codigo código HTTP
 * @param cuerpo valor que acepta {@code JsonEscritor} (Map, Lista, record, etc.)
 */
public record Respuesta(int codigo, Object cuerpo) {

    /**
     * Crea una respuesta 200.
     *
     * @param cuerpo valor a escribir como JSON
     * @return la respuesta
     */
    public static Respuesta ok(Object cuerpo) {
        return new Respuesta(200, cuerpo);
    }
}
