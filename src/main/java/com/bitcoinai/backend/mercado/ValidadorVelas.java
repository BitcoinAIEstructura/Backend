package com.bitcoinai.backend.mercado;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Objects;

/**
 * Comprueba que una serie de velas sea coherente antes de usarla.
 */
public final class ValidadorVelas {

    private ValidadorVelas() {
    }

    /**
     * Valida una serie de velas. Reglas:
     * <ul>
     *   <li>ordenadas por tiempo de apertura, de la más antigua a la más reciente, sin duplicados;</li>
     *   <li>precios positivos y finitos; volumen no negativo;</li>
     *   <li>máximo &gt;= mínimo, y apertura y cierre dentro de ese rango;</li>
     *   <li>tiempo de cierre no anterior al de apertura.</li>
     * </ul>
     * Complejidad: O(n), un solo recorrido hacia adelante.
     *
     * @param velas serie a validar (puede estar vacía)
     * @throws MercadoException con la posición y el motivo de la primera vela inválida
     */
    public static void validar(ListaDoble<Vela> velas) {
        Objects.requireNonNull(velas, "velas");
        Vela anterior = null;
        int indice = 0;
        for (Vela vela : velas) {
            validarVela(vela, indice);
            if (anterior != null) {
                if (vela.tiempoApertura() == anterior.tiempoApertura()) {
                    throw invalida(indice, "vela duplicada (tiempoApertura " + vela.tiempoApertura() + ")");
                }
                if (vela.tiempoApertura() < anterior.tiempoApertura()) {
                    throw invalida(indice, "velas desordenadas (tiempoApertura " + vela.tiempoApertura()
                            + " es anterior a " + anterior.tiempoApertura() + ")");
                }
            }
            anterior = vela;
            indice++;
        }
    }

    private static void validarVela(Vela vela, int indice) {
        if (vela == null) {
            throw invalida(indice, "la vela es nula");
        }
        if (!positivo(vela.apertura()) || !positivo(vela.maximo())
                || !positivo(vela.minimo()) || !positivo(vela.cierre())) {
            throw invalida(indice, "los precios deben ser positivos");
        }
        if (vela.maximo() < vela.minimo()) {
            throw invalida(indice, "el máximo es menor que el mínimo");
        }
        if (vela.maximo() < Math.max(vela.apertura(), vela.cierre())
                || vela.minimo() > Math.min(vela.apertura(), vela.cierre())) {
            throw invalida(indice, "la apertura o el cierre están fuera del rango mínimo-máximo");
        }
        if (!(vela.volumen() >= 0) || Double.isInfinite(vela.volumen())) {
            throw invalida(indice, "el volumen debe ser cero o positivo");
        }
        if (vela.tiempoCierre() < vela.tiempoApertura()) {
            throw invalida(indice, "el tiempo de cierre es anterior al de apertura");
        }
    }

    private static boolean positivo(double valor) {
        return valor > 0 && Double.isFinite(valor);
    }

    private static MercadoException invalida(int indice, String motivo) {
        return new MercadoException("Vela inválida en la posición " + indice + ": " + motivo);
    }
}
