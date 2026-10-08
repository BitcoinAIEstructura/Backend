package com.bitcoinai.backend.estrategia;

import static com.bitcoinai.backend.estrategia.Apoyo.num;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.indicadores.PuntoIndicador;
import com.bitcoinai.backend.indicadores.Series;
import com.bitcoinai.backend.indicadores.Sma;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Cruce de medias móviles simples.
 *
 * <ul>
 *   <li>COMPRAR en la vela en que la SMA corta cruza hacia arriba la larga.</li>
 *   <li>VENDER en la vela en que la cruza hacia abajo.</li>
 *   <li>MANTENER en el resto.</li>
 * </ul>
 * La confianza crece con la separación entre las medias tras el cruce.
 * Complejidad de {@link #evaluar}: O(n), por el cálculo de las dos SMA.
 */
public class CruceDeMedias implements Estrategia {

    private final int corta;
    private final int larga;

    /** Crea la estrategia con las medias habituales de 20 y 50. */
    public CruceDeMedias() {
        this(20, 50);
    }

    /**
     * Crea la estrategia.
     *
     * @param corta periodo de la media corta (1 o más)
     * @param larga periodo de la media larga (mayor que la corta)
     * @throws IllegalArgumentException si los periodos no cumplen esas reglas
     */
    public CruceDeMedias(int corta, int larga) {
        if (corta < 1 || larga <= corta) {
            throw new IllegalArgumentException("Se necesita 1 <= corta < larga; recibido corta="
                    + corta + ", larga=" + larga);
        }
        this.corta = corta;
        this.larga = larga;
    }

    @Override
    public String nombre() {
        return "cruce";
    }

    @Override
    public Map<String, Object> parametros() {
        Map<String, Object> parametros = new LinkedHashMap<>();
        parametros.put("corta", corta);
        parametros.put("larga", larga);
        return parametros;
    }

    /** Hacen falta dos puntos de la media larga para detectar un cruce. */
    @Override
    public int velasMinimas() {
        return larga + 1;
    }

    @Override
    public Decision evaluar(ListaDoble<Vela> velas) {
        if (velas == null || velas.tamanio() < velasMinimas()) {
            return Apoyo.faltanVelas(velas, velasMinimas());
        }
        // Solo interesan los dos valores más recientes de cada media (antes y ahora).
        ListaDoble<PuntoIndicador> mediaCorta = Series.ultimos(new Sma(corta).calcular(velas), 2);
        ListaDoble<PuntoIndicador> mediaLarga = Series.ultimos(new Sma(larga).calcular(velas), 2);
        double precio = velas.ultimo().cierre();
        int antes = Apoyo.signo(mediaCorta.primero().valor() - mediaLarga.primero().valor(), precio);
        double diferencia = mediaCorta.ultimo().valor() - mediaLarga.ultimo().valor();
        int ahora = Apoyo.signo(diferencia, precio);
        String medias = "la SMA " + corta + " (" + num(mediaCorta.ultimo().valor()) + ") "
                + "%s la SMA " + larga + " (" + num(mediaLarga.ultimo().valor()) + ")";

        if (antes <= 0 && ahora > 0) {
            return Apoyo.decidir(velas, Senal.COMPRAR, Apoyo.confianzaPorDistancia(diferencia / precio),
                    "Cruce alcista: " + String.format(medias, "cruzó por encima de") + "; posible inicio de tendencia alcista.");
        }
        if (antes >= 0 && ahora < 0) {
            return Apoyo.decidir(velas, Senal.VENDER, Apoyo.confianzaPorDistancia(diferencia / precio),
                    "Cruce bajista: " + String.format(medias, "cruzó por debajo de") + "; posible inicio de tendencia bajista.");
        }
        String estado = ahora > 0 ? "sigue por encima de" : ahora < 0 ? "sigue por debajo de" : "está igual que";
        return Apoyo.decidir(velas, Senal.MANTENER, Apoyo.CONFIANZA_NEUTRA,
                "Sin cruce nuevo: " + String.format(medias, estado) + ".");
    }

    @Override
    public Map<String, Double> indicadoresActuales(ListaDoble<Vela> velas) {
        Map<String, Double> valores = new LinkedHashMap<>();
        Apoyo.agregarUltimo(valores, "smaCorta", new Sma(corta).calcular(velas));
        Apoyo.agregarUltimo(valores, "smaLarga", new Sma(larga).calcular(velas));
        return valores;
    }
}
