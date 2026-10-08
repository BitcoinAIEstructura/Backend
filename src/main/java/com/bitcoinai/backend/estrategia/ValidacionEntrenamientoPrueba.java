package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Objects;

/**
 * Validación honesta de una estrategia con división entrenamiento/prueba.
 *
 * <ol>
 *   <li>Las velas se dividen en dos tramos consecutivos: el primero (por defecto
 *       70 %) es el de entrenamiento y el resto el de prueba.</li>
 *   <li>Cada combinación de parámetros candidata se prueba con un backtest
 *       <b>solo sobre las velas de entrenamiento</b> (se le entrega una lista que
 *       no contiene ninguna vela de prueba), y se elige la de mayor rentabilidad.</li>
 *   <li>La elegida se prueba en el tramo de prueba, que nunca participó en la
 *       elección. Las velas de entrenamiento solo le sirven ahí como historial para
 *       calentar los indicadores, sin operar en ellas.</li>
 * </ol>
 * Si a la estrategia le va mucho peor en prueba que en entrenamiento, los
 * parámetros se ajustaron al pasado (sobreajuste) y no hay que confiar en ellos.
 *
 * <p>Complejidad: O(c · n²), con c candidatos.
 */
public class ValidacionEntrenamientoPrueba {

    /** Fracción de entrenamiento por defecto. */
    public static final double FRACCION_POR_DEFECTO = 0.7;

    private final Backtester backtester;
    private final double fraccionEntrenamiento;

    /**
     * Crea la validación.
     *
     * @param backtester            backtester (capital y comisión) usado en ambos tramos
     * @param fraccionEntrenamiento fracción de velas para entrenar, entre 0 y 1 sin incluirlos
     * @throws IllegalArgumentException si la fracción está fuera de rango
     */
    public ValidacionEntrenamientoPrueba(Backtester backtester, double fraccionEntrenamiento) {
        this.backtester = Objects.requireNonNull(backtester, "backtester");
        if (!(fraccionEntrenamiento > 0 && fraccionEntrenamiento < 1)) {
            throw new IllegalArgumentException("La fracción de entrenamiento debe estar entre 0 y 1: "
                    + fraccionEntrenamiento);
        }
        this.fraccionEntrenamiento = fraccionEntrenamiento;
    }

    /**
     * Elige parámetros en entrenamiento y los mide en prueba.
     *
     * @param candidatos la misma estrategia con distintos parámetros (al menos una)
     * @param velas      todas las velas, de la más antigua a la más reciente
     * @return el resultado de ambos tramos
     * @throws IllegalArgumentException si no hay candidatos
     */
    public ResultadoValidacion ejecutar(Lista<Estrategia> candidatos, ListaDoble<Vela> velas) {
        if (candidatos.estaVacia()) {
            throw new IllegalArgumentException("Se necesita al menos un candidato");
        }
        // El 1e-9 evita que un error de redondeo (p. ej. 83,999999…) quite una vela.
        int velasEntrenamiento = (int) Math.floor(velas.tamanio() * fraccionEntrenamiento + 1e-9);
        ListaDoble<Vela> entrenamiento = primeras(velas, velasEntrenamiento);

        Lista<ResumenCandidato> resumenes = new Lista<>();
        Estrategia mejor = null;
        ResultadoBacktest mejorResultado = null;
        for (Estrategia candidato : candidatos) {
            ResultadoBacktest resultado = backtester.ejecutar(candidato, entrenamiento);
            resumenes.agregar(new ResumenCandidato(candidato.parametros(),
                    resultado.rentabilidadTotal(), resultado.numeroOperaciones()));
            if (mejorResultado == null || resultado.rentabilidadTotal() > mejorResultado.rentabilidadTotal()) {
                mejor = candidato;
                mejorResultado = resultado;
            }
        }

        ResultadoBacktest prueba = backtester.ejecutar(mejor, velas, velasEntrenamiento);
        return new ResultadoValidacion(mejor.nombre(), fraccionEntrenamiento, velasEntrenamiento,
                velas.tamanio() - velasEntrenamiento, mejor.parametros(), resumenes, mejorResultado, prueba);
    }

    /** Copia de las primeras n velas. Complejidad: O(n). */
    private static ListaDoble<Vela> primeras(ListaDoble<Vela> velas, int n) {
        ListaDoble<Vela> copia = new ListaDoble<>();
        for (Vela vela : velas) {
            if (copia.tamanio() == n) {
                break;
            }
            copia.agregarFinal(vela);
        }
        return copia;
    }
}
