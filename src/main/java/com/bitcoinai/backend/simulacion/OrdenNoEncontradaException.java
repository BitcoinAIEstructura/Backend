package com.bitcoinai.backend.simulacion;

/** No existe una orden con ese id. */
public class OrdenNoEncontradaException extends RuntimeException {

    /**
     * Crea la excepción.
     *
     * @param id id buscado
     */
    public OrdenNoEncontradaException(long id) {
        super("No existe la orden #" + id);
    }
}
