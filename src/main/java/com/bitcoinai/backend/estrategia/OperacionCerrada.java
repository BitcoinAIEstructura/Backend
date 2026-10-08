package com.bitcoinai.backend.estrategia;

/**
 * Una operación larga completa del backtest: compra y luego venta.
 *
 * @param tiempoEntrada tiempo de apertura de la vela en que se compró
 * @param precioEntrada precio de compra (apertura de esa vela)
 * @param tiempoSalida  tiempo de apertura de la vela en que se vendió
 * @param precioSalida  precio de venta
 * @param cantidadBtc   BTC comprados (ya descontada la comisión de compra)
 * @param comisiones    comisiones de compra y venta, en USDT
 * @param ganancia      capital al salir − capital al entrar, en USDT (negativa si hubo pérdida)
 * @param rentabilidad  ganancia / capital al entrar (0,05 = 5 %)
 * @param motivoSalida  por qué se vendió
 */
public record OperacionCerrada(
        long tiempoEntrada,
        double precioEntrada,
        long tiempoSalida,
        double precioSalida,
        double cantidadBtc,
        double comisiones,
        double ganancia,
        double rentabilidad,
        String motivoSalida) {
}
