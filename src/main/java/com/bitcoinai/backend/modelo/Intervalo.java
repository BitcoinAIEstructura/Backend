package com.bitcoinai.backend.modelo;

/**
 * Intervalos de vela soportados, con el código que usa Binance y su duración.
 */
public enum Intervalo {

    /** 1 minuto. */
    M1("1m", 60_000L),
    /** 5 minutos. */
    M5("5m", 5 * 60_000L),
    /** 15 minutos. */
    M15("15m", 15 * 60_000L),
    /** 1 hora. */
    H1("1h", 60 * 60_000L),
    /** 4 horas. */
    H4("4h", 4 * 60 * 60_000L),
    /** 1 día. */
    D1("1d", 24 * 60 * 60_000L);

    private final String codigo;
    private final long milisegundos;

    Intervalo(String codigo, long milisegundos) {
        this.codigo = codigo;
        this.milisegundos = milisegundos;
    }

    /**
     * Devuelve el código que usa Binance, por ejemplo "1d".
     *
     * @return el código del intervalo
     */
    public String codigo() {
        return codigo;
    }

    /**
     * Devuelve cuánto dura el intervalo.
     *
     * @return la duración en milisegundos
     */
    public long milisegundos() {
        return milisegundos;
    }

    /**
     * Busca el intervalo que corresponde a un código de Binance.
     *
     * @param codigo código como "1m", "4h" o "1d"
     * @return el intervalo correspondiente
     * @throws IllegalArgumentException si el código no está soportado
     */
    public static Intervalo desdeCodigo(String codigo) {
        for (Intervalo intervalo : values()) {
            if (intervalo.codigo.equals(codigo)) {
                return intervalo;
            }
        }
        throw new IllegalArgumentException(
                "Intervalo no soportado: " + codigo + ". Use 1m, 5m, 15m, 1h, 4h o 1d");
    }
}
