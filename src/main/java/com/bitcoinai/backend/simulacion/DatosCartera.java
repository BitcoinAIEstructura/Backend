package com.bitcoinai.backend.simulacion;

/**
 * Datos mínimos para reconstruir una {@link Cartera} (lo que se guarda en disco).
 *
 * @param saldoInicial      USDT con que empezó
 * @param saldoUsdt         USDT disponibles
 * @param btc               BTC en cartera
 * @param costoPosicion     USDT que costó el BTC actual, con comisiones
 * @param gananciaRealizada ganancia acumulada de las ventas
 * @param comisionesPagadas total de comisiones
 */
public record DatosCartera(
        double saldoInicial,
        double saldoUsdt,
        double btc,
        double costoPosicion,
        double gananciaRealizada,
        double comisionesPagadas) {

    /**
     * Valida que los datos tengan sentido.
     *
     * @throws IllegalArgumentException si algún valor es imposible (negativo o no finito)
     */
    public DatosCartera {
        if (!(saldoInicial > 0) || !noNegativo(saldoUsdt) || !noNegativo(btc)
                || !noNegativo(costoPosicion) || !noNegativo(comisionesPagadas)
                || !Double.isFinite(gananciaRealizada) || Double.isInfinite(saldoInicial)) {
            throw new IllegalArgumentException("Datos de cartera imposibles");
        }
    }

    private static boolean noNegativo(double valor) {
        return valor >= 0 && Double.isFinite(valor);
    }
}
