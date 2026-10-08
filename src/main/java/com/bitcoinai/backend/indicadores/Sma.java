package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Map;

/**
 * Media móvil simple (SMA) de los cierres.
 *
 * <p>Fórmula: SMAₜ = (xₜ + xₜ₋₁ + … + xₜ₋ₚ₊₁) / p.
 *
 * <p>Se mantiene una ventana ({@link ListaDoble}) con los últimos p cierres y su
 * suma acumulada: al entrar un cierre se suma, y cuando la ventana pasa de p se
 * resta el más antiguo y se recorta con {@code conservarUltimos(p)}. Así cada
 * vela cuesta O(1) y el total es O(n), en vez de O(n·p) si se sumara la ventana
 * completa en cada vela. Memoria extra: O(p).
 */
public class Sma implements Indicador {

    private final int periodo;

    /**
     * Crea el indicador.
     *
     * @param periodo número de cierres que se promedian (1 o más)
     * @throws IllegalArgumentException si el periodo es menor que 1
     */
    public Sma(int periodo) {
        if (periodo < 1) {
            throw new IllegalArgumentException("El periodo debe ser al menos 1: " + periodo);
        }
        this.periodo = periodo;
    }

    @Override
    public String nombre() {
        return "sma";
    }

    @Override
    public Map<String, Object> parametros() {
        return Series.soloPeriodo(periodo);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Complejidad: O(n) en tiempo, O(p) en memoria extra.
     */
    @Override
    public ListaDoble<PuntoIndicador> calcular(ListaDoble<Vela> velas) {
        ListaDoble<PuntoIndicador> resultado = new ListaDoble<>();
        if (velas == null) {
            return resultado;
        }
        ListaDoble<Double> ventana = new ListaDoble<>();
        double suma = 0;
        for (Vela vela : velas) {
            ventana.agregarFinal(vela.cierre());
            suma += vela.cierre();
            if (ventana.tamanio() > periodo) {
                suma -= ventana.primero();
                ventana.conservarUltimos(periodo);
            }
            if (ventana.tamanio() == periodo) {
                resultado.agregarFinal(new PuntoIndicador(vela.tiempoApertura(), suma / periodo));
            }
        }
        return resultado;
    }
}
