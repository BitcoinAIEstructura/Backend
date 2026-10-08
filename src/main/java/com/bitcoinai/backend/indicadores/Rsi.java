package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Map;

/**
 * Índice de Fuerza Relativa (RSI) con el suavizado de Wilder.
 *
 * <p>Fórmula, con cambioₜ = cierreₜ − cierreₜ₋₁, gananciaₜ = max(cambioₜ, 0) y
 * pérdidaₜ = max(−cambioₜ, 0):
 * <ul>
 *   <li>Primeros promedios: media simple de las primeras p ganancias y pérdidas.</li>
 *   <li>Después (Wilder): promedioₜ = (promedioₜ₋₁·(p − 1) + valorₜ) / p.</li>
 *   <li>RS = promedioGanancias / promedioPérdidas; RSI = 100 − 100 / (1 + RS).</li>
 * </ul>
 * Va de 0 a 100. El primer punto sale en la vela p (hacen falta p + 1 velas para p cambios).
 *
 * <p><b>Casos límite (decisión):</b> si no hay pérdidas el RSI es 100; si no hay
 * ganancias es 0; y si no hay ni ganancias ni pérdidas (serie plana) es <b>50</b>,
 * porque no hay impulso hacia ningún lado. Así nunca se produce NaN, que además
 * no se puede escribir en JSON.
 *
 * <p>Complejidad: O(n), un recorrido hacia adelante; memoria extra O(1).
 */
public class Rsi implements Indicador {

    private final int periodo;

    /**
     * Crea el indicador.
     *
     * @param periodo periodo de suavizado (1 o más; el habitual es 14)
     * @throws IllegalArgumentException si el periodo es menor que 1
     */
    public Rsi(int periodo) {
        if (periodo < 1) {
            throw new IllegalArgumentException("El periodo debe ser al menos 1: " + periodo);
        }
        this.periodo = periodo;
    }

    @Override
    public String nombre() {
        return "rsi";
    }

    @Override
    public Map<String, Object> parametros() {
        return Series.soloPeriodo(periodo);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Complejidad: O(n).
     */
    @Override
    public ListaDoble<PuntoIndicador> calcular(ListaDoble<Vela> velas) {
        ListaDoble<PuntoIndicador> resultado = new ListaDoble<>();
        if (velas == null) {
            return resultado;
        }
        Vela anterior = null;
        int cambios = 0;
        double promedioGanancia = 0;
        double promedioPerdida = 0;
        for (Vela vela : velas) {
            if (anterior != null) {
                double cambio = vela.cierre() - anterior.cierre();
                double ganancia = Math.max(cambio, 0);
                double perdida = Math.max(-cambio, 0);
                cambios++;
                if (cambios <= periodo) {
                    // Durante el calentamiento se acumula para la media simple inicial.
                    promedioGanancia += ganancia;
                    promedioPerdida += perdida;
                    if (cambios == periodo) {
                        promedioGanancia /= periodo;
                        promedioPerdida /= periodo;
                        resultado.agregarFinal(new PuntoIndicador(vela.tiempoApertura(),
                                rsi(promedioGanancia, promedioPerdida)));
                    }
                } else {
                    promedioGanancia = (promedioGanancia * (periodo - 1) + ganancia) / periodo;
                    promedioPerdida = (promedioPerdida * (periodo - 1) + perdida) / periodo;
                    resultado.agregarFinal(new PuntoIndicador(vela.tiempoApertura(),
                            rsi(promedioGanancia, promedioPerdida)));
                }
            }
            anterior = vela;
        }
        return resultado;
    }

    private static double rsi(double promedioGanancia, double promedioPerdida) {
        if (promedioPerdida == 0) {
            return promedioGanancia == 0 ? 50.0 : 100.0;
        }
        return 100.0 - 100.0 / (1.0 + promedioGanancia / promedioPerdida);
    }
}
