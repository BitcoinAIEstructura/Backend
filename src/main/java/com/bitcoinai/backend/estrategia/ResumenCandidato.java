package com.bitcoinai.backend.estrategia;

import java.util.Map;

/**
 * Cómo le fue a una combinación de parámetros en el periodo de entrenamiento.
 *
 * @param parametros        parámetros probados
 * @param rentabilidad      rentabilidad total en entrenamiento (fracción)
 * @param numeroOperaciones operaciones cerradas en entrenamiento
 */
public record ResumenCandidato(Map<String, Object> parametros, double rentabilidad, int numeroOperaciones) {
}
