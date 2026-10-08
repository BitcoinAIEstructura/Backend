package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import java.util.Map;

/**
 * Resultado de la validación entrenamiento/prueba.
 *
 * @param estrategia            nombre de la estrategia
 * @param fraccionEntrenamiento fracción de velas usada para entrenar (0,7 = 70 %)
 * @param velasEntrenamiento    velas del periodo de entrenamiento
 * @param velasPrueba           velas del periodo de prueba
 * @param parametrosElegidos    parámetros que mejor rindieron en entrenamiento
 * @param candidatos            cómo rindió cada combinación en entrenamiento
 * @param entrenamiento         backtest de los parámetros elegidos en entrenamiento
 * @param prueba                backtest de esos mismos parámetros en el periodo de prueba, nunca visto
 */
public record ResultadoValidacion(
        String estrategia,
        double fraccionEntrenamiento,
        int velasEntrenamiento,
        int velasPrueba,
        Map<String, Object> parametrosElegidos,
        Lista<ResumenCandidato> candidatos,
        ResultadoBacktest entrenamiento,
        ResultadoBacktest prueba) {
}
