package com.bitcoinai.backend.indicadores;

/**
 * Un valor de un indicador en un momento dado.
 *
 * @param tiempo tiempo de apertura de la vela a la que corresponde (ms desde 1970, UTC)
 * @param valor  valor del indicador
 */
public record PuntoIndicador(long tiempo, double valor) {
}
