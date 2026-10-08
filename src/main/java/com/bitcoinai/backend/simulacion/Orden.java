package com.bitcoinai.backend.simulacion;

/**
 * Orden simulada. Es inmutable: cada cambio de estado crea una orden nueva con
 * el mismo id, así nadie puede modificar una orden guardada en la cola o en el registro.
 *
 * @param id              número único, creciente
 * @param tipo            compra o venta
 * @param monto           USDT a comprar o a vender; null en una venta de todo el BTC
 *                        hasta que se ejecuta (ahí pasa a ser lo obtenido)
 * @param todo            true si es una venta de todo el BTC
 * @param estado          estado actual
 * @param creadaEn        cuándo se creó (ms)
 * @param ejecutadaEn     cuándo se procesó (ejecutada o rechazada), o null
 * @param precioEjecucion precio al que se procesó, o null
 * @param cantidadBtc     BTC comprados o vendidos, o null
 * @param comision        comisión cobrada en USDT, o null
 * @param motivo          por qué se creó: "manual", "señal del bot: …", "stop-loss: …"
 * @param detalle         resultado o razón del rechazo o la cancelación, o null
 */
public record Orden(
        long id,
        TipoOrden tipo,
        Double monto,
        boolean todo,
        EstadoOrden estado,
        long creadaEn,
        Long ejecutadaEn,
        Double precioEjecucion,
        Double cantidadBtc,
        Double comision,
        String motivo,
        String detalle) {

    /** Orden recién creada, pendiente. */
    static Orden nueva(long id, TipoOrden tipo, Double monto, boolean todo, long creadaEn, String motivo) {
        return new Orden(id, tipo, monto, todo, EstadoOrden.PENDIENTE, creadaEn, null, null, null, null, motivo, null);
    }

    /** Misma orden con otro estado y detalle. */
    Orden conEstado(EstadoOrden nuevoEstado, String nuevoDetalle) {
        return new Orden(id, tipo, monto, todo, nuevoEstado, creadaEn, ejecutadaEn, precioEjecucion,
                cantidadBtc, comision, motivo, nuevoDetalle);
    }

    /** Misma orden, ejecutada con el resultado de la cartera. */
    Orden ejecutada(long momento, double precio, Cartera.Ejecucion ejecucion, String nuevoDetalle) {
        return new Orden(id, tipo, todo ? ejecucion.montoUsdt() : monto, todo, EstadoOrden.EJECUTADA, creadaEn,
                momento, precio, ejecucion.cantidadBtc(), ejecucion.comision(), motivo, nuevoDetalle);
    }

    /** Misma orden, rechazada al precio dado. */
    Orden rechazada(long momento, double precio, String razon) {
        return new Orden(id, tipo, monto, todo, EstadoOrden.RECHAZADA, creadaEn, momento, precio,
                null, null, motivo, razon);
    }
}
