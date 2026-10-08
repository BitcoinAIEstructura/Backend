package com.bitcoinai.backend.simulacion;

/**
 * Algo que pasó en la simulación, para el historial.
 *
 * @param momento     cuándo pasó (ms desde 1970, UTC)
 * @param tipo        qué pasó
 * @param idOrden     orden relacionada, o null
 * @param descripcion una frase en español
 */
public record Evento(long momento, TipoEvento tipo, Long idOrden, String descripcion) {
}
