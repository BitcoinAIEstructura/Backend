package com.bitcoinai.backend.modelo;

/**
 * Vela (candlestick) de un intervalo de mercado.
 *
 * <p>No valida sus datos al construirse para poder representar lo que llega de la
 * fuente tal cual; la validación la hace {@code mercado.ValidadorVelas}.
 *
 * @param tiempoApertura momento de apertura, en milisegundos desde 1970 (UTC)
 * @param apertura       precio de apertura
 * @param maximo         precio máximo del intervalo
 * @param minimo         precio mínimo del intervalo
 * @param cierre         precio de cierre
 * @param volumen        volumen negociado en la moneda base (BTC)
 * @param tiempoCierre   momento de cierre, en milisegundos desde 1970 (UTC)
 */
public record Vela(
        long tiempoApertura,
        double apertura,
        double maximo,
        double minimo,
        double cierre,
        double volumen,
        long tiempoCierre) {
}
