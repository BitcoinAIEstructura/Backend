package com.bitcoinai.backend.simulacion;

/** Tipos de evento del historial. */
public enum TipoEvento {
    /** Se creó una orden. */
    ORDEN_CREADA,
    /** Se ejecutó una orden. */
    ORDEN_EJECUTADA,
    /** Se canceló una orden pendiente. */
    ORDEN_CANCELADA,
    /** Se deshizo la última orden creada. */
    ORDEN_DESHECHA,
    /** Se rechazó una orden. */
    ORDEN_RECHAZADA,
    /** El bot tomó una decisión. */
    DECISION_BOT,
    /** El bot vendió por stop-loss. */
    STOP_LOSS,
    /** El bot vendió por take-profit. */
    TAKE_PROFIT,
    /** Se inició el bot. */
    BOT_INICIADO,
    /** Se detuvo el bot. */
    BOT_DETENIDO,
    /** Un ciclo del bot falló. */
    ERROR_BOT
}
