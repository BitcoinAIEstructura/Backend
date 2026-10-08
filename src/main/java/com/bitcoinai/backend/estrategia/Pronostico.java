package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Map;
import java.util.Objects;

/**
 * Pronóstico simple derivado de la decisión de una estrategia (normalmente la combinada).
 *
 * <p>COMPRAR → SUBE, VENDER → BAJA, MANTENER → LATERAL, con la misma confianza.
 * Incluye las frases que lo justifican y el valor actual de los indicadores usados.
 *
 * <p><b>Aviso: Resultado de pruebas con datos históricos; no es asesoría financiera
 * ni garantiza ganancias.</b>
 *
 * @param direccion     hacia dónde se espera que vaya el precio
 * @param confianza     entre 0 y 1
 * @param justificacion frases que explican el pronóstico
 * @param indicadores   nombre del indicador → valor actual
 * @param aviso         siempre {@link #AVISO}
 */
public record Pronostico(
        Direccion direccion,
        double confianza,
        Lista<String> justificacion,
        Map<String, Double> indicadores,
        String aviso) {

    /** Aviso fijo que acompaña todo pronóstico y todo backtest. */
    public static final String AVISO =
            "Resultado de pruebas con datos históricos; no es asesoría financiera ni garantiza ganancias";

    /**
     * Arma el pronóstico de una decisión ya tomada.
     *
     * @param estrategia la estrategia que tomó la decisión
     * @param velas      las velas con que la tomó
     * @param decision   la decisión
     * @return el pronóstico
     */
    public static Pronostico desde(Estrategia estrategia, ListaDoble<Vela> velas, Decision decision) {
        Objects.requireNonNull(estrategia, "estrategia");
        Objects.requireNonNull(decision, "decision");
        return new Pronostico(direccionDe(decision.senal()), decision.confianza(),
                estrategia.justificacion(velas, decision), estrategia.indicadoresActuales(velas), AVISO);
    }

    /**
     * Traduce una señal a dirección esperada.
     *
     * @param senal la señal
     * @return SUBE, BAJA o LATERAL
     */
    public static Direccion direccionDe(Senal senal) {
        return switch (senal) {
            case COMPRAR -> Direccion.SUBE;
            case VENDER -> Direccion.BAJA;
            case MANTENER -> Direccion.LATERAL;
        };
    }
}
