package com.bitcoinai.backend.api;

/**
 * Atiende una ruta. Puede lanzar {@link ApiException} para responder un error
 * al cliente, o {@code MercadoException} si falla la fuente de mercado (502).
 */
@FunctionalInterface
public interface Manejador {

    /**
     * Atiende la petición.
     *
     * @param peticion datos de la petición
     * @return la respuesta a enviar como JSON
     */
    Respuesta manejar(Peticion peticion);
}
