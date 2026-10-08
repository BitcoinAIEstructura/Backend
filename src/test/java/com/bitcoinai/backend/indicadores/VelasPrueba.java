package com.bitcoinai.backend.indicadores;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;

/** Utilidades para armar velas y comparar series en las pruebas de indicadores. */
final class VelasPrueba {

    static final long PASO = 60_000L;

    private VelasPrueba() {
    }

    /** Velas planas (apertura = máximo = mínimo = cierre) en t = 0, 1 min, 2 min... */
    static ListaDoble<Vela> deCierres(double... cierres) {
        ListaDoble<Vela> velas = new ListaDoble<>();
        for (int i = 0; i < cierres.length; i++) {
            double c = cierres[i];
            velas.agregarFinal(new Vela(i * PASO, c, c, c, c, 1, i * PASO + PASO - 1));
        }
        return velas;
    }

    /** n cierres iguales a {@code valor}. */
    static ListaDoble<Vela> constantes(int n, double valor) {
        double[] cierres = new double[n];
        java.util.Arrays.fill(cierres, valor);
        return deCierres(cierres);
    }

    /** n cierres que suben (o bajan, con paso negativo) desde {@code inicio}. */
    static ListaDoble<Vela> lineales(int n, double inicio, double paso) {
        double[] cierres = new double[n];
        for (int i = 0; i < n; i++) {
            cierres[i] = inicio + i * paso;
        }
        return deCierres(cierres);
    }

    /** Comprueba valores y que el tiempo de cada punto sea el de la vela {@code primerIndice + i}. */
    static void assertSerie(ListaDoble<PuntoIndicador> serie, int primerIndice, double... esperados) {
        assertEquals(esperados.length, serie.tamanio(), "cantidad de puntos");
        int i = 0;
        for (PuntoIndicador punto : serie) {
            assertEquals(esperados[i], punto.valor(), 1e-9, "valor del punto " + i);
            assertEquals((primerIndice + i) * PASO, punto.tiempo(), "tiempo del punto " + i);
            i++;
        }
    }

    /** Comprueba que todos los puntos valgan {@code valor}. */
    static void assertTodos(ListaDoble<PuntoIndicador> serie, double valor) {
        for (PuntoIndicador punto : serie) {
            assertEquals(valor, punto.valor(), 1e-9);
        }
    }
}
