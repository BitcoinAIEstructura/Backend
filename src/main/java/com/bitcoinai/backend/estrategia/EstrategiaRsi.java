package com.bitcoinai.backend.estrategia;

import static com.bitcoinai.backend.estrategia.Apoyo.num;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.indicadores.PuntoIndicador;
import com.bitcoinai.backend.indicadores.Rsi;
import com.bitcoinai.backend.indicadores.Series;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Estrategia de reversión con el RSI.
 *
 * <ul>
 *   <li>COMPRAR cuando el RSI estuvo por debajo de la sobreventa (30) y vuelve a subir por encima.</li>
 *   <li>VENDER cuando estuvo por encima de la sobrecompra (70) y vuelve a bajar.</li>
 *   <li>MANTENER en el resto.</li>
 * </ul>
 * Se espera el giro en vez de comprar apenas entra en sobreventa, porque una caída
 * fuerte puede seguir cayendo. La confianza crece con lo extremo que llegó a estar el RSI.
 * Complejidad de {@link #evaluar}: O(n), por el cálculo del RSI.
 */
public class EstrategiaRsi implements Estrategia {

    private final int periodo;
    private final double sobreventa;
    private final double sobrecompra;

    /** Crea la estrategia con RSI 14 y niveles 30 y 70. */
    public EstrategiaRsi() {
        this(14, 30, 70);
    }

    /**
     * Crea la estrategia.
     *
     * @param periodo     periodo del RSI (1 o más)
     * @param sobreventa  nivel de sobreventa (entre 0 y 50)
     * @param sobrecompra nivel de sobrecompra (entre 50 y 100)
     * @throws IllegalArgumentException si algún parámetro está fuera de rango
     */
    public EstrategiaRsi(int periodo, double sobreventa, double sobrecompra) {
        if (periodo < 1) {
            throw new IllegalArgumentException("El periodo del RSI debe ser al menos 1");
        }
        if (!(sobreventa > 0 && sobreventa < 50 && sobrecompra > 50 && sobrecompra < 100)) {
            throw new IllegalArgumentException("Se necesita 0 < sobreventa < 50 < sobrecompra < 100");
        }
        this.periodo = periodo;
        this.sobreventa = sobreventa;
        this.sobrecompra = sobrecompra;
    }

    @Override
    public String nombre() {
        return "rsi";
    }

    @Override
    public Map<String, Object> parametros() {
        Map<String, Object> parametros = new LinkedHashMap<>();
        parametros.put("periodo", periodo);
        parametros.put("sobreventa", sobreventa);
        parametros.put("sobrecompra", sobrecompra);
        return parametros;
    }

    /** El RSI da su primer punto con periodo + 1 velas, y hacen falta dos puntos. */
    @Override
    public int velasMinimas() {
        return periodo + 2;
    }

    @Override
    public Decision evaluar(ListaDoble<Vela> velas) {
        if (velas == null || velas.tamanio() < velasMinimas()) {
            return Apoyo.faltanVelas(velas, velasMinimas());
        }
        ListaDoble<PuntoIndicador> ultimos = Series.ultimos(new Rsi(periodo).calcular(velas), 2);
        double antes = ultimos.primero().valor();
        double ahora = ultimos.ultimo().valor();

        if (antes < sobreventa && ahora >= sobreventa) {
            double confianza = 0.6 + Math.min(0.4, (sobreventa - antes) / sobreventa);
            return Apoyo.decidir(velas, Senal.COMPRAR, confianza, "El RSI salió de sobreventa: pasó de "
                    + num(antes) + " a " + num(ahora) + " cruzando " + num(sobreventa) + "; posible rebote al alza.");
        }
        if (antes > sobrecompra && ahora <= sobrecompra) {
            double confianza = 0.6 + Math.min(0.4, (antes - sobrecompra) / (100 - sobrecompra));
            return Apoyo.decidir(velas, Senal.VENDER, confianza, "El RSI salió de sobrecompra: pasó de "
                    + num(antes) + " a " + num(ahora) + " cruzando " + num(sobrecompra) + "; posible corrección a la baja.");
        }
        String zona;
        if (ahora < sobreventa) {
            zona = "está en sobreventa; se espera que vuelva a subir de " + num(sobreventa) + " para comprar";
        } else if (ahora > sobrecompra) {
            zona = "está en sobrecompra; se espera que vuelva a bajar de " + num(sobrecompra) + " para vender";
        } else {
            zona = "está en zona neutral, sin señal de giro";
        }
        return Apoyo.decidir(velas, Senal.MANTENER, Apoyo.CONFIANZA_NEUTRA, "El RSI (" + num(ahora) + ") " + zona + ".");
    }

    @Override
    public Map<String, Double> indicadoresActuales(ListaDoble<Vela> velas) {
        Map<String, Double> valores = new LinkedHashMap<>();
        Apoyo.agregarUltimo(valores, "rsi", new Rsi(periodo).calcular(velas));
        return valores;
    }
}
