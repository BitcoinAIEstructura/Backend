package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;

/**
 * Las tres series del MACD. La señal y el histograma empiezan más tarde que la
 * línea MACD (necesitan su propio calentamiento), así que tienen menos puntos.
 *
 * @param macd       EMA rápida − EMA lenta
 * @param senal      EMA de la línea MACD
 * @param histograma macd − señal
 */
public record ResultadoMacd(
        ListaDoble<PuntoIndicador> macd,
        ListaDoble<PuntoIndicador> senal,
        ListaDoble<PuntoIndicador> histograma) {
}
