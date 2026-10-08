package com.bitcoinai.backend.persistencia;

/** Un archivo guardado no tiene el formato esperado. */
public class DatosDanadosException extends RuntimeException {

    /**
     * Crea la excepción.
     *
     * @param mensaje qué está mal y dónde
     */
    public DatosDanadosException(String mensaje) {
        super(mensaje);
    }
}
