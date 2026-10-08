package com.bitcoinai.backend.simulacion;

import com.bitcoinai.backend.modelo.Intervalo;

/**
 * Configuración del bot simulado.
 *
 * @param segundosEntreCiclos cada cuántos segundos decide (1 a 86 400)
 * @param intervalo           intervalo de las velas que analiza ("1m" … "1d")
 * @param cantidadVelas       cuántas velas analiza (2 a 1000)
 * @param riesgo              fracción del saldo que usa en cada compra (0,2 = 20 %)
 * @param stopLoss            pérdida desde el costo promedio que dispara la venta (0,05 = 5 %)
 * @param takeProfit          ganancia desde el costo promedio que dispara la venta (0,10 = 10 %)
 */
public record ConfiguracionBot(
        int segundosEntreCiclos,
        String intervalo,
        int cantidadVelas,
        double riesgo,
        double stopLoss,
        double takeProfit) {

    /**
     * Valida los campos.
     *
     * @throws IllegalArgumentException con un mensaje claro si alguno está fuera de rango
     */
    public ConfiguracionBot {
        if (segundosEntreCiclos < 1 || segundosEntreCiclos > 86_400) {
            throw new IllegalArgumentException("'segundosEntreCiclos' debe estar entre 1 y 86400");
        }
        Intervalo.desdeCodigo(intervalo); // lanza IllegalArgumentException con los valores permitidos
        if (cantidadVelas < 2 || cantidadVelas > 1000) {
            throw new IllegalArgumentException("'cantidadVelas' debe estar entre 2 y 1000");
        }
        if (!(riesgo > 0 && riesgo <= 1)) {
            throw new IllegalArgumentException("'riesgo' debe ser mayor que 0 y como máximo 1");
        }
        if (!(stopLoss > 0 && stopLoss < 1)) {
            throw new IllegalArgumentException("'stopLoss' debe estar entre 0 y 1, sin incluirlos");
        }
        if (!(takeProfit > 0 && takeProfit <= 10)) {
            throw new IllegalArgumentException("'takeProfit' debe ser mayor que 0 y como máximo 10");
        }
    }

    /**
     * Valores por defecto: cada 60 s, 200 velas de 1 h, riesgo 20 %, stop-loss 5 % y take-profit 10 %.
     *
     * @return la configuración por defecto
     */
    public static ConfiguracionBot porDefecto() {
        return new ConfiguracionBot(60, "1h", 200, 0.20, 0.05, 0.10);
    }
}
