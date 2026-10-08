package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;

/**
 * Las tres series de las Bandas de Bollinger, alineadas punto a punto.
 *
 * @param media    media móvil simple
 * @param superior media + k·desviación
 * @param inferior media − k·desviación
 */
public record ResultadoBollinger(
        ListaDoble<PuntoIndicador> media,
        ListaDoble<PuntoIndicador> superior,
        ListaDoble<PuntoIndicador> inferior) {
}
