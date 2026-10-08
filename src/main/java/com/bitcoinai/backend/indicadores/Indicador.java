package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Indicador técnico calculado sobre los precios de cierre de una serie de velas.
 *
 * <p>Las primeras velas, mientras no hay datos suficientes (periodo de
 * calentamiento), no generan punto. Si hay menos velas que las necesarias, el
 * resultado es una lista vacía, nunca un error.
 */
public interface Indicador {

    /**
     * Devuelve el nombre corto del indicador, por ejemplo "rsi".
     *
     * @return el nombre
     */
    String nombre();

    /**
     * Devuelve los parámetros con que se creó, por ejemplo {periodo=14}.
     *
     * @return parámetros en orden
     */
    Map<String, Object> parametros();

    /**
     * Calcula la serie principal del indicador.
     *
     * @param velas velas de la más antigua a la más reciente
     * @return un punto por cada vela después del calentamiento
     */
    ListaDoble<PuntoIndicador> calcular(ListaDoble<Vela> velas);

    /**
     * Calcula todas las series del indicador con su nombre. Por defecto solo la
     * principal, como "valor"; MACD y Bollinger devuelven tres series.
     *
     * @param velas velas de la más antigua a la más reciente
     * @return nombre de la serie → puntos, en orden
     */
    default Map<String, ListaDoble<PuntoIndicador>> calcularSeries(ListaDoble<Vela> velas) {
        Map<String, ListaDoble<PuntoIndicador>> series = new LinkedHashMap<>();
        series.put("valor", calcular(velas));
        return series;
    }
}
