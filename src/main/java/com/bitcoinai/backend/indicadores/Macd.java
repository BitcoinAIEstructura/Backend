package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * MACD (Moving Average Convergence Divergence).
 *
 * <p>Fórmula:
 * <ul>
 *   <li>línea MACD = EMA(rápida) − EMA(lenta) de los cierres;</li>
 *   <li>señal = EMA(señal) de la línea MACD;</li>
 *   <li>histograma = MACD − señal.</li>
 * </ul>
 * Valores habituales: 12, 26 y 9. La línea MACD empieza en la vela lenta − 1 y
 * la señal {@code señal − 1} puntos después.
 *
 * <p>Complejidad: O(n). Se calculan tres EMA (O(n) cada una) y dos restas
 * alineadas (O(n)).
 */
public class Macd implements Indicador {

    private final int rapido;
    private final int lento;
    private final int senal;

    /**
     * Crea el indicador.
     *
     * @param rapido periodo de la EMA rápida (1 o más)
     * @param lento  periodo de la EMA lenta (mayor que rápido)
     * @param senal  periodo de la EMA de la señal (1 o más)
     * @throws IllegalArgumentException si los periodos no cumplen esas reglas
     */
    public Macd(int rapido, int lento, int senal) {
        if (rapido < 1 || senal < 1) {
            throw new IllegalArgumentException("Los periodos del MACD deben ser al menos 1");
        }
        if (lento <= rapido) {
            throw new IllegalArgumentException("El periodo lento del MACD debe ser mayor que el rápido");
        }
        this.rapido = rapido;
        this.lento = lento;
        this.senal = senal;
    }

    /** Crea el MACD con los valores habituales 12, 26 y 9. */
    public Macd() {
        this(12, 26, 9);
    }

    @Override
    public String nombre() {
        return "macd";
    }

    @Override
    public Map<String, Object> parametros() {
        Map<String, Object> parametros = new LinkedHashMap<>();
        parametros.put("rapido", rapido);
        parametros.put("lento", lento);
        parametros.put("senal", senal);
        return parametros;
    }

    /**
     * Calcula las tres series.
     * Complejidad: O(n).
     *
     * @param velas velas de la más antigua a la más reciente
     * @return línea MACD, señal e histograma
     */
    public ResultadoMacd calcularCompleto(ListaDoble<Vela> velas) {
        ListaDoble<PuntoIndicador> cierres = Series.cierres(velas);
        ListaDoble<PuntoIndicador> emaLenta = Series.ema(cierres, lento);

        // La EMA rápida empieza (lento − rápido) velas antes que la lenta. Para
        // alinearlas solo sirven sus valores más recientes, tantos como tenga la
        // lenta: Series.ultimos los toma recorriendo hacia atrás desde la cola.
        ListaDoble<PuntoIndicador> emaRapida = Series.ultimos(Series.ema(cierres, rapido), emaLenta.tamanio());
        ListaDoble<PuntoIndicador> lineaMacd = Series.restar(emaRapida, emaLenta);

        ListaDoble<PuntoIndicador> lineaSenal = Series.ema(lineaMacd, senal);
        // Igual para el histograma: los últimos valores del MACD, tantos como la señal.
        ListaDoble<PuntoIndicador> histograma =
                Series.restar(Series.ultimos(lineaMacd, lineaSenal.tamanio()), lineaSenal);
        return new ResultadoMacd(lineaMacd, lineaSenal, histograma);
    }

    /**
     * {@inheritDoc}
     *
     * <p>La serie principal es la línea MACD. Complejidad: O(n).
     */
    @Override
    public ListaDoble<PuntoIndicador> calcular(ListaDoble<Vela> velas) {
        return calcularCompleto(velas).macd();
    }

    /** Devuelve "macd", "senal" e "histograma". Complejidad: O(n). */
    @Override
    public Map<String, ListaDoble<PuntoIndicador>> calcularSeries(ListaDoble<Vela> velas) {
        ResultadoMacd resultado = calcularCompleto(velas);
        Map<String, ListaDoble<PuntoIndicador>> series = new LinkedHashMap<>();
        series.put("macd", resultado.macd());
        series.put("senal", resultado.senal());
        series.put("histograma", resultado.histograma());
        return series;
    }
}
