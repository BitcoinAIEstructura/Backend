package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.indicadores.PuntoIndicador;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Locale;
import java.util.Map;

/** Utilidades compartidas por las estrategias. */
final class Apoyo {

    /**
     * Confianza de un MANTENER cuando no pasa nada. Es baja a propósito: en la
     * estrategia combinada, una señal clara (confianza 0,6 o más) de una sola
     * estrategia debe poder ganarle a dos "no pasa nada".
     */
    static final double CONFIANZA_NEUTRA = 0.25;

    /** Por debajo de esta fracción del precio, una diferencia se considera cero (evita cruces por ruido numérico). */
    private static final double TOLERANCIA_RELATIVA = 1e-9;

    private Apoyo() {
    }

    /**
     * Confianza de una señal según qué tan marcada es: 0,6 como base, más hasta
     * 0,4 según la distancia relativa al precio (0,4 % o más da confianza 1).
     */
    static double confianzaPorDistancia(double distanciaRelativa) {
        return 0.6 + Math.min(0.4, Math.abs(distanciaRelativa) * 100);
    }

    /** Signo de un valor, tratando como 0 lo que es despreciable frente a la escala (el precio). */
    static int signo(double valor, double escala) {
        double tolerancia = Math.abs(escala) * TOLERANCIA_RELATIVA;
        if (valor > tolerancia) {
            return 1;
        }
        if (valor < -tolerancia) {
            return -1;
        }
        return 0;
    }

    /** Número con dos decimales y punto decimal, para los motivos. */
    static String num(double valor) {
        return String.format(Locale.ROOT, "%.2f", valor);
    }

    /** Decisión sobre la última vela (su tiempo y su cierre). */
    static Decision decidir(ListaDoble<Vela> velas, Senal senal, double confianza, String motivo) {
        Vela ultima = velas.ultimo();
        return new Decision(ultima.tiempoApertura(), senal, ultima.cierre(),
                Math.max(0, Math.min(1, confianza)), motivo);
    }

    /** MANTENER con confianza 0 porque todavía no hay velas suficientes. */
    static Decision faltanVelas(ListaDoble<Vela> velas, int necesarias) {
        int hay = velas == null ? 0 : velas.tamanio();
        long tiempo = hay == 0 ? 0 : velas.ultimo().tiempoApertura();
        double precio = hay == 0 ? 0 : velas.ultimo().cierre();
        return new Decision(tiempo, Senal.MANTENER, precio, 0.0,
                "Faltan velas para decidir: se necesitan al menos " + necesarias + " y hay " + hay + ".");
    }

    /** Agrega el último valor de la serie, si tiene alguno. */
    static void agregarUltimo(Map<String, Double> mapa, String clave, ListaDoble<PuntoIndicador> serie) {
        if (!serie.estaVacia()) {
            mapa.put(clave, serie.ultimo().valor());
        }
    }
}
