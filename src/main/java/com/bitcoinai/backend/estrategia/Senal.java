package com.bitcoinai.backend.estrategia;

/** Lo que una estrategia recomienda hacer. */
public enum Senal {
    /** Abrir una posición larga (comprar BTC). */
    COMPRAR,
    /** Cerrar la posición (vender el BTC). */
    VENDER,
    /** No hacer nada. */
    MANTENER
}
