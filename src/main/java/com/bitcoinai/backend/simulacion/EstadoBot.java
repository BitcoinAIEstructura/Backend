package com.bitcoinai.backend.simulacion;

import com.bitcoinai.backend.estrategia.Decision;

/**
 * Estado del bot simulado.
 *
 * @param activo          true si está en marcha
 * @param estrategia      nombre de la estrategia que consulta
 * @param configuracion   configuración actual (o la última usada)
 * @param ciclos          ciclos ejecutados desde que se creó
 * @param ultimoCiclo     cuándo terminó el último ciclo (ms), o null
 * @param ultimaDecision  última decisión de la estrategia, o null
 * @param ultimoError     error del último ciclo, o null si salió bien
 */
public record EstadoBot(
        boolean activo,
        String estrategia,
        ConfiguracionBot configuracion,
        long ciclos,
        Long ultimoCiclo,
        Decision ultimaDecision,
        String ultimoError) {
}
