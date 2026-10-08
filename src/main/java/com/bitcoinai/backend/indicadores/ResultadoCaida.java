package com.bitcoinai.backend.indicadores;

/**
 * Resultado de la máxima caída (drawdown máximo).
 *
 * <p>Si la serie está vacía todos los campos son 0. Si nunca baja, la caída es 0
 * y el pico y el valle son el primer punto.
 *
 * @param caidaMaxima fracción entre 0 y 1 (0,25 = cayó un 25 % desde el pico)
 * @param tiempoPico  momento del pico previo a la peor caída
 * @param valorPico   valor en el pico
 * @param tiempoValle momento del punto más bajo de esa caída
 * @param valorValle  valor en el valle
 */
public record ResultadoCaida(
        double caidaMaxima,
        long tiempoPico,
        double valorPico,
        long tiempoValle,
        double valorValle) {
}
