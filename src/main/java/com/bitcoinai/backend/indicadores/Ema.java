package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Map;

/**
 * Media móvil exponencial (EMA) de los cierres.
 *
 * <p>Fórmula: α = 2 / (p + 1). La primera EMA es la media simple de los primeros
 * p cierres (en la vela p − 1); después EMAₜ = α·cierreₜ + (1 − α)·EMAₜ₋₁.
 * Da más peso a los precios recientes que la SMA. Con p = 1 es igual al cierre.
 *
 * <p>Complejidad: O(n), un recorrido hacia adelante; memoria extra O(1) aparte del resultado.
 */
public class Ema implements Indicador {

    private final int periodo;

    /**
     * Crea el indicador.
     *
     * @param periodo periodo (1 o más)
     * @throws IllegalArgumentException si el periodo es menor que 1
     */
    public Ema(int periodo) {
        if (periodo < 1) {
            throw new IllegalArgumentException("El periodo debe ser al menos 1: " + periodo);
        }
        this.periodo = periodo;
    }

    @Override
    public String nombre() {
        return "ema";
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
        return Series.ema(Series.cierres(velas), periodo);
    }
}
