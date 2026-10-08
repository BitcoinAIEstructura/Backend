package com.bitcoinai.backend.simulacion;

/** Estado de una orden en su ciclo de vida. */
public enum EstadoOrden {
    /** Esperando en la cola. */
    PENDIENTE,
    /** Sacada de la cola; se está consultando el precio para ejecutarla. */
    PROCESANDO,
    /** Ejecutada: la cartera ya cambió. */
    EJECUTADA,
    /** Cancelada o deshecha antes de ejecutarse. */
    CANCELADA,
    /** No se pudo ejecutar (saldo o BTC insuficiente). */
    RECHAZADA
}
