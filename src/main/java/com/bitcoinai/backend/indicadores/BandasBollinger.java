package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Bandas de Bollinger.
 *
 * <p>Fórmula, sobre los últimos p cierres:
 * <ul>
 *   <li>media = SMA(p);</li>
 *   <li>σ = desviación estándar poblacional = √(Σx²/p − media²), como en la definición de Bollinger;</li>
 *   <li>superior = media + k·σ; inferior = media − k·σ.</li>
 * </ul>
 * Valores habituales: p = 20, k = 2.
 *
 * <p>Igual que la SMA, usa una ventana ListaDoble con suma y suma de cuadrados
 * acumuladas, así que cuesta O(n) en total. Para no perder precisión al restar
 * números grandes (precios de ~80 000 al cuadrado), los cierres se guardan
 * desplazados restándoles el primero; la varianza no cambia con ese desplazamiento.
 */
public class BandasBollinger implements Indicador {

    private final int periodo;
    private final double desviaciones;

    /**
     * Crea el indicador.
     *
     * @param periodo      número de cierres de la ventana (1 o más)
     * @param desviaciones cuántas desviaciones estándar se alejan las bandas (mayor que 0)
     * @throws IllegalArgumentException si algún parámetro es inválido
     */
    public BandasBollinger(int periodo, double desviaciones) {
        if (periodo < 1) {
            throw new IllegalArgumentException("El periodo debe ser al menos 1: " + periodo);
        }
        if (!(desviaciones > 0) || Double.isInfinite(desviaciones)) {
            throw new IllegalArgumentException("Las desviaciones deben ser un número positivo: " + desviaciones);
        }
        this.periodo = periodo;
        this.desviaciones = desviaciones;
    }

    @Override
    public String nombre() {
        return "bollinger";
    }

    @Override
    public Map<String, Object> parametros() {
        Map<String, Object> parametros = Series.soloPeriodo(periodo);
        parametros.put("desviaciones", desviaciones);
        return parametros;
    }

    /**
     * Calcula las tres bandas.
     * Complejidad: O(n) en tiempo, O(p) en memoria extra.
     *
     * @param velas velas de la más antigua a la más reciente
     * @return media, banda superior e inferior
     */
    public ResultadoBollinger calcularBandas(ListaDoble<Vela> velas) {
        ListaDoble<PuntoIndicador> media = new ListaDoble<>();
        ListaDoble<PuntoIndicador> superior = new ListaDoble<>();
        ListaDoble<PuntoIndicador> inferior = new ListaDoble<>();
        if (velas == null || velas.estaVacia()) {
            return new ResultadoBollinger(media, superior, inferior);
        }
        double referencia = velas.primero().cierre();
        ListaDoble<Double> ventana = new ListaDoble<>();
        double suma = 0;
        double sumaCuadrados = 0;
        for (Vela vela : velas) {
            double x = vela.cierre() - referencia;
            ventana.agregarFinal(x);
            suma += x;
            sumaCuadrados += x * x;
            if (ventana.tamanio() > periodo) {
                double viejo = ventana.primero();
                suma -= viejo;
                sumaCuadrados -= viejo * viejo;
                ventana.conservarUltimos(periodo);
            }
            if (ventana.tamanio() == periodo) {
                double mediaDesplazada = suma / periodo;
                double varianza = Math.max(0, sumaCuadrados / periodo - mediaDesplazada * mediaDesplazada);
                double banda = desviaciones * Math.sqrt(varianza);
                double valorMedia = mediaDesplazada + referencia;
                long tiempo = vela.tiempoApertura();
                media.agregarFinal(new PuntoIndicador(tiempo, valorMedia));
                superior.agregarFinal(new PuntoIndicador(tiempo, valorMedia + banda));
                inferior.agregarFinal(new PuntoIndicador(tiempo, valorMedia - banda));
            }
        }
        return new ResultadoBollinger(media, superior, inferior);
    }

    /**
     * {@inheritDoc}
     *
     * <p>La serie principal es la media. Complejidad: O(n).
     */
    @Override
    public ListaDoble<PuntoIndicador> calcular(ListaDoble<Vela> velas) {
        return calcularBandas(velas).media();
    }

    /** Devuelve "media", "superior" e "inferior". Complejidad: O(n). */
    @Override
    public Map<String, ListaDoble<PuntoIndicador>> calcularSeries(ListaDoble<Vela> velas) {
        ResultadoBollinger bandas = calcularBandas(velas);
        Map<String, ListaDoble<PuntoIndicador>> series = new LinkedHashMap<>();
        series.put("media", bandas.media());
        series.put("superior", bandas.superior());
        series.put("inferior", bandas.inferior());
        return series;
    }
}
