package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Map;

/**
 * Estrategia de trading: mira las velas hasta ahora y decide comprar, vender o mantener.
 *
 * <p>Regla de oro: {@link #evaluar} solo puede usar las velas que recibe. Así el
 * backtest garantiza que nunca se mira el futuro.
 */
public interface Estrategia {

    /**
     * Devuelve el nombre corto, por ejemplo "cruce".
     *
     * @return el nombre
     */
    String nombre();

    /**
     * Devuelve los parámetros con que se creó.
     *
     * @return parámetros en orden
     */
    Map<String, Object> parametros();

    /**
     * Devuelve cuántas velas necesita como mínimo para poder dar una señal.
     *
     * @return número de velas
     */
    int velasMinimas();

    /**
     * Decide qué hacer en la última vela recibida. Con menos de
     * {@link #velasMinimas()} velas devuelve MANTENER con confianza 0.
     *
     * @param velasHastaAhora velas de la más antigua a la más reciente; no se modifican
     * @return la decisión
     */
    Decision evaluar(ListaDoble<Vela> velasHastaAhora);

    /**
     * Devuelve el último valor de los indicadores que usa, para explicar la decisión.
     *
     * @param velas velas de la más antigua a la más reciente
     * @return nombre del indicador → valor (vacío si no hay datos suficientes)
     */
    Map<String, Double> indicadoresActuales(ListaDoble<Vela> velas);

    /**
     * Devuelve las frases que justifican una decisión. Por defecto, su motivo.
     *
     * @param velas    las mismas velas con que se tomó la decisión
     * @param decision la decisión a justificar
     * @return una o más frases
     */
    default Lista<String> justificacion(ListaDoble<Vela> velas, Decision decision) {
        Lista<String> frases = new Lista<>();
        frases.agregar(decision.motivo());
        return frases;
    }
}
