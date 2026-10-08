package com.bitcoinai.backend.simulacion;

/**
 * Foto de la cartera valorada a un precio.
 *
 * @param precioActual        precio de BTC usado para valorar
 * @param saldoUsdt           USDT disponibles
 * @param btc                 BTC en cartera
 * @param costoPromedio       USDT pagados por BTC en la posición actual, con comisiones (0 si no hay BTC)
 * @param valorBtc            btc × precioActual
 * @param valorTotal          saldoUsdt + valorBtc
 * @param gananciaNoRealizada valorBtc − lo que costó ese BTC
 * @param gananciaRealizada   ganancia acumulada de las ventas ya hechas
 * @param gananciaTotal       valorTotal − saldoInicial
 * @param rentabilidad        gananciaTotal / saldoInicial (0,05 = 5 %)
 * @param comisionesPagadas   total de comisiones en USDT
 * @param saldoInicial        USDT con que empezó la simulación
 */
public record EstadoCartera(
        double precioActual,
        double saldoUsdt,
        double btc,
        double costoPromedio,
        double valorBtc,
        double valorTotal,
        double gananciaNoRealizada,
        double gananciaRealizada,
        double gananciaTotal,
        double rentabilidad,
        double comisionesPagadas,
        double saldoInicial) {
}
