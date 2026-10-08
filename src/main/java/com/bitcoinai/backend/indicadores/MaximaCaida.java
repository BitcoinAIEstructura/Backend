package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;

/**
 * Máxima caída (drawdown máximo): la mayor bajada porcentual desde un pico hasta
 * un punto posterior.
 *
 * <p>Fórmula: caídaₜ = (picoₜ − xₜ) / picoₜ, donde picoₜ es el máximo visto hasta t;
 * el resultado es el mayor caídaₜ.
 *
 * <p>Se recorre la serie <b>una sola vez</b> hacia adelante, llevando el pico
 * máximo visto hasta el momento: O(n) en tiempo y O(1) en memoria extra.
 * También sirve para la curva de capital del backtest, por eso acepta puntos.
 */
public final class MaximaCaida {

    private MaximaCaida() {
    }

    /**
     * Máxima caída de los cierres de una serie de velas.
     * Complejidad: O(n).
     *
     * @param velas velas de la más antigua a la más reciente
     * @return la caída máxima y dónde ocurrió
     */
    public static ResultadoCaida deVelas(ListaDoble<Vela> velas) {
        return dePuntos(Series.cierres(velas));
    }

    /**
     * Máxima caída de una serie de valores positivos (precios o capital).
     * Complejidad: O(n), un solo recorrido.
     *
     * @param serie puntos en orden cronológico
     * @return la caída máxima y dónde ocurrió
     */
    public static ResultadoCaida dePuntos(ListaDoble<PuntoIndicador> serie) {
        if (serie == null || serie.estaVacia()) {
            return new ResultadoCaida(0, 0, 0, 0, 0);
        }
        PuntoIndicador pico = serie.primero();
        ResultadoCaida peor = new ResultadoCaida(0, pico.tiempo(), pico.valor(), pico.tiempo(), pico.valor());
        for (PuntoIndicador punto : serie) {
            if (punto.valor() > pico.valor()) {
                pico = punto;
            }
            double caida = (pico.valor() - punto.valor()) / pico.valor();
            if (caida > peor.caidaMaxima()) {
                peor = new ResultadoCaida(caida, pico.tiempo(), pico.valor(), punto.tiempo(), punto.valor());
            }
        }
        return peor;
    }
}
