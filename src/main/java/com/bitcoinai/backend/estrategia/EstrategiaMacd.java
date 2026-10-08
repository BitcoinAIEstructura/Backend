package com.bitcoinai.backend.estrategia;

import static com.bitcoinai.backend.estrategia.Apoyo.num;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.indicadores.Macd;
import com.bitcoinai.backend.indicadores.PuntoIndicador;
import com.bitcoinai.backend.indicadores.ResultadoMacd;
import com.bitcoinai.backend.indicadores.Series;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Estrategia de cruces del MACD con su línea de señal (cambio de signo del histograma).
 *
 * <ul>
 *   <li>COMPRAR cuando el MACD cruza hacia arriba su señal.</li>
 *   <li>VENDER cuando la cruza hacia abajo.</li>
 *   <li>MANTENER en el resto.</li>
 * </ul>
 * La confianza crece con el tamaño del histograma relativo al precio.
 * Complejidad de {@link #evaluar}: O(n), por el cálculo del MACD.
 */
public class EstrategiaMacd implements Estrategia {

    private final Macd macd;
    private final int lento;
    private final int senal;

    /** Crea la estrategia con el MACD habitual 12, 26, 9. */
    public EstrategiaMacd() {
        this(12, 26, 9);
    }

    /**
     * Crea la estrategia.
     *
     * @param rapido periodo de la EMA rápida
     * @param lento  periodo de la EMA lenta (mayor que la rápida)
     * @param senal  periodo de la línea de señal
     * @throws IllegalArgumentException si los periodos son inválidos
     */
    public EstrategiaMacd(int rapido, int lento, int senal) {
        this.macd = new Macd(rapido, lento, senal);
        this.lento = lento;
        this.senal = senal;
    }

    @Override
    public String nombre() {
        return "macd";
    }

    @Override
    public Map<String, Object> parametros() {
        return macd.parametros();
    }

    /** El histograma empieza en la vela lento + señal − 2, y hacen falta dos puntos. */
    @Override
    public int velasMinimas() {
        return lento + senal;
    }

    @Override
    public Decision evaluar(ListaDoble<Vela> velas) {
        if (velas == null || velas.tamanio() < velasMinimas()) {
            return Apoyo.faltanVelas(velas, velasMinimas());
        }
        ResultadoMacd resultado = macd.calcularCompleto(velas);
        ListaDoble<PuntoIndicador> histograma = Series.ultimos(resultado.histograma(), 2);
        double precio = velas.ultimo().cierre();
        int antes = Apoyo.signo(histograma.primero().valor(), precio);
        double valorAhora = histograma.ultimo().valor();
        int ahora = Apoyo.signo(valorAhora, precio);
        String valores = " (MACD " + num(resultado.macd().ultimo().valor())
                + ", señal " + num(resultado.senal().ultimo().valor()) + ")";

        if (antes <= 0 && ahora > 0) {
            return Apoyo.decidir(velas, Senal.COMPRAR, Apoyo.confianzaPorDistancia(valorAhora / precio),
                    "El MACD cruzó por encima de su señal" + valores + "; el impulso se vuelve alcista.");
        }
        if (antes >= 0 && ahora < 0) {
            return Apoyo.decidir(velas, Senal.VENDER, Apoyo.confianzaPorDistancia(valorAhora / precio),
                    "El MACD cruzó por debajo de su señal" + valores + "; el impulso se vuelve bajista.");
        }
        String estado = ahora > 0 ? "sigue por encima de" : ahora < 0 ? "sigue por debajo de" : "está igual que";
        return Apoyo.decidir(velas, Senal.MANTENER, Apoyo.CONFIANZA_NEUTRA,
                "Sin cruce nuevo: el MACD " + estado + " su señal" + valores + ".");
    }

    @Override
    public Map<String, Double> indicadoresActuales(ListaDoble<Vela> velas) {
        ResultadoMacd resultado = macd.calcularCompleto(velas);
        Map<String, Double> valores = new LinkedHashMap<>();
        Apoyo.agregarUltimo(valores, "macd", resultado.macd());
        Apoyo.agregarUltimo(valores, "senalMacd", resultado.senal());
        Apoyo.agregarUltimo(valores, "histogramaMacd", resultado.histograma());
        return valores;
    }
}
