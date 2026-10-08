package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.indicadores.PuntoIndicador;
import java.util.Map;

/**
 * Resultado y métricas de un backtest. Las rentabilidades, la tasa de aciertos
 * y la caída son fracciones: 0,25 significa 25 %.
 *
 * @param estrategia                   nombre de la estrategia
 * @param parametros                   parámetros de la estrategia
 * @param capitalInicial               USDT al empezar
 * @param comision                     comisión por operación (0,001 = 0,1 %)
 * @param capitalFinal                 USDT al terminar (con la posición cerrada)
 * @param rentabilidadTotal            capitalFinal / capitalInicial − 1
 * @param rentabilidadComprarYMantener comprar en la primera apertura y vender en el último cierre, con comisiones
 * @param numeroOperaciones            operaciones cerradas
 * @param tasaGanadoras                fracción de operaciones con ganancia
 * @param caidaMaxima                  mayor caída de la curva de capital desde un pico
 * @param factorBeneficio              suma de ganancias / suma de pérdidas; null si no hubo pérdidas
 * @param comisionesPagadas            total de comisiones en USDT
 * @param velasAnalizadas              velas en el periodo operado
 * @param numeroDecisiones             decisiones tomadas (una por vela operada)
 * @param tiempoInicio                 apertura de la primera vela operada
 * @param tiempoFin                    cierre de la última vela operada
 * @param operaciones                  operaciones cerradas, en orden
 * @param decisionesRecientes          últimas decisiones de comprar o vender, la más reciente primero
 * @param curvaCapital                 valor de la cartera al cierre de cada vela
 */
public record ResultadoBacktest(
        String estrategia,
        Map<String, Object> parametros,
        double capitalInicial,
        double comision,
        double capitalFinal,
        double rentabilidadTotal,
        double rentabilidadComprarYMantener,
        int numeroOperaciones,
        double tasaGanadoras,
        double caidaMaxima,
        Double factorBeneficio,
        double comisionesPagadas,
        int velasAnalizadas,
        int numeroDecisiones,
        long tiempoInicio,
        long tiempoFin,
        Lista<OperacionCerrada> operaciones,
        Lista<Decision> decisionesRecientes,
        ListaDoble<PuntoIndicador> curvaCapital) {
}
