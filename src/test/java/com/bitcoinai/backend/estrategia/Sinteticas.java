package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;

/** Series de velas sintéticas y utilidades para las pruebas de estrategias. */
final class Sinteticas {

    static final long DIA = 86_400_000L;

    /** Índice de la vela donde cambia la tendencia en {@link #alcistaTrasCaida()} y {@link #bajistaTrasSubida()}. */
    static final int GIRO = 59;

    private Sinteticas() {
    }

    /** Velas con apertura y cierre dados (máximo y mínimo los envuelven), una por día desde t = 0. */
    static ListaDoble<Vela> velas(double[] aperturas, double[] cierres) {
        ListaDoble<Vela> velas = new ListaDoble<>();
        for (int i = 0; i < cierres.length; i++) {
            double maximo = Math.max(aperturas[i], cierres[i]);
            double minimo = Math.min(aperturas[i], cierres[i]);
            velas.agregarFinal(new Vela(i * DIA, aperturas[i], maximo, minimo, cierres[i], 1, i * DIA + DIA - 1));
        }
        return velas;
    }

    /** Velas planas (apertura = cierre). */
    static ListaDoble<Vela> deCierres(double... cierres) {
        return velas(cierres, cierres);
    }

    /** Baja de 200 a 141 (vela 59) y luego sube 1,5 por vela: tendencia alcista tras una caída. Forma de V. */
    static ListaDoble<Vela> alcistaTrasCaida() {
        double[] cierres = new double[120];
        for (int i = 0; i < cierres.length; i++) {
            cierres[i] = i <= GIRO ? 200 - i : 141 + 1.5 * (i - GIRO);
        }
        return deCierres(cierres);
    }

    /** Sube de 100 a 159 (vela 59) y luego baja 1,5 por vela: tendencia bajista tras una subida. */
    static ListaDoble<Vela> bajistaTrasSubida() {
        double[] cierres = new double[120];
        for (int i = 0; i < cierres.length; i++) {
            cierres[i] = i <= GIRO ? 100 + i : 159 - 1.5 * (i - GIRO);
        }
        return deCierres(cierres);
    }

    /** Mercado lateral sin movimiento. */
    static ListaDoble<Vela> lateralPlano() {
        double[] cierres = new double[120];
        java.util.Arrays.fill(cierres, 100);
        return deCierres(cierres);
    }

    /** Mercado lateral que oscila 100, 101, 100, 101... */
    static ListaDoble<Vela> lateralZigzag() {
        double[] cierres = new double[120];
        for (int i = 0; i < cierres.length; i++) {
            cierres[i] = i % 2 == 0 ? 100 : 101;
        }
        return deCierres(cierres);
    }

    /**
     * Evalúa la estrategia en cada prefijo de las velas (como hace el backtest) y
     * devuelve las señales distintas de MANTENER como "COMPRAR@63".
     */
    static Lista<String> senales(Estrategia estrategia, ListaDoble<Vela> velas) {
        Lista<String> senales = new Lista<>();
        ListaDoble<Vela> hastaAhora = new ListaDoble<>();
        int indice = 0;
        for (Vela vela : velas) {
            hastaAhora.agregarFinal(vela);
            Decision decision = estrategia.evaluar(hastaAhora);
            if (decision.senal() != Senal.MANTENER) {
                senales.agregar(decision.senal() + "@" + indice);
            }
            indice++;
        }
        return senales;
    }

    /** Índice de una señal "COMPRAR@63" → 63. */
    static int indiceDe(String senal) {
        return Integer.parseInt(senal.substring(senal.indexOf('@') + 1));
    }

    static String texto(Lista<String> lista) {
        StringBuilder sb = new StringBuilder("[");
        for (String s : lista) {
            if (sb.length() > 1) {
                sb.append(", ");
            }
            sb.append(s);
        }
        return sb.append(']').toString();
    }
}
