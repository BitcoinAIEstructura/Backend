package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Map;

/**
 * Volatilidad: desviación estándar de los retornos logarítmicos en una ventana.
 *
 * <p>Fórmula: rₜ = ln(cierreₜ / cierreₜ₋₁). Sobre los últimos p retornos,
 * σ = √((Σr² − (Σr)²/p) / (p − 1)) (desviación muestral, porque estima la
 * volatilidad a partir de una muestra). No está anualizada: es la volatilidad por
 * vela (con velas diarias, multiplicar por √365 da la anual). El primer punto
 * sale en la vela p (hacen falta p + 1 cierres para p retornos).
 *
 * <p>Usa una ventana ListaDoble con suma y suma de cuadrados acumuladas:
 * O(n) en total, O(p) de memoria extra.
 */
public class Volatilidad implements Indicador {

    private final int periodo;

    /**
     * Crea el indicador.
     *
     * @param periodo número de retornos de la ventana (2 o más, por la división entre p − 1)
     * @throws IllegalArgumentException si el periodo es menor que 2
     */
    public Volatilidad(int periodo) {
        if (periodo < 2) {
            throw new IllegalArgumentException("El periodo de la volatilidad debe ser al menos 2: " + periodo);
        }
        this.periodo = periodo;
    }

    @Override
    public String nombre() {
        return "volatilidad";
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
        double sumaCuadrados = 0;
        Vela anterior = null;
        for (Vela vela : velas) {
            if (anterior != null) {
                double retorno = Math.log(vela.cierre() / anterior.cierre());
                ventana.agregarFinal(retorno);
                suma += retorno;
                sumaCuadrados += retorno * retorno;
                if (ventana.tamanio() > periodo) {
                    double viejo = ventana.primero();
                    suma -= viejo;
                    sumaCuadrados -= viejo * viejo;
                    ventana.conservarUltimos(periodo);
                }
                if (ventana.tamanio() == periodo) {
                    double varianza = Math.max(0, (sumaCuadrados - suma * suma / periodo) / (periodo - 1));
                    resultado.agregarFinal(new PuntoIndicador(vela.tiempoApertura(), Math.sqrt(varianza)));
                }
            }
            anterior = vela;
        }
        return resultado;
    }
}
