package com.bitcoinai.backend.simulacion;

/**
 * Destino de los eventos en tiempo real de la simulación ("orden", "cartera",
 * "senal"). El libro de órdenes y el bot solo conocen esta interfaz; quien la
 * implementa (el {@code api.Publicador} con SSE) vive en la capa HTTP. Así la
 * simulación no depende de HTTP y en las pruebas se puede reemplazar.
 *
 * <p>Las implementaciones no deben bloquear: se llama con candados tomados.
 */
@FunctionalInterface
public interface PublicadorEventos {

    /** Publicador que descarta todo, para cuando no hay tiempo real. */
    PublicadorEventos NINGUNO = (tipo, datos) -> { };

    /**
     * Publica un evento.
     *
     * @param tipo  nombre del evento, por ejemplo "orden"
     * @param datos datos que acepta {@code JsonEscritor} (records, Map, Lista…)
     */
    void publicar(String tipo, Object datos);
}
