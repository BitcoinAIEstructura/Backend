package com.bitcoinai.backend.modelo;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class ModeloTest {

    @Test
    void velaGuardaSusCamposYSeComparaPorValor() {
        Vela a = new Vela(1000, 10, 12, 9, 11, 5, 1999);
        assertEquals(1000, a.tiempoApertura());
        assertEquals(10, a.apertura());
        assertEquals(12, a.maximo());
        assertEquals(9, a.minimo());
        assertEquals(11, a.cierre());
        assertEquals(5, a.volumen());
        assertEquals(1999, a.tiempoCierre());
        assertEquals(a, new Vela(1000, 10, 12, 9, 11, 5, 1999));
        assertNotEquals(a, new Vela(1000, 10, 12, 9, 11.5, 5, 1999));
    }

    @Test
    void intervalosTienenCodigoDeBinanceYDuracion() {
        assertEquals("1m", Intervalo.M1.codigo());
        assertEquals(60_000L, Intervalo.M1.milisegundos());
        assertEquals(300_000L, Intervalo.M5.milisegundos());
        assertEquals(900_000L, Intervalo.M15.milisegundos());
        assertEquals(3_600_000L, Intervalo.H1.milisegundos());
        assertEquals(14_400_000L, Intervalo.H4.milisegundos());
        assertEquals("1d", Intervalo.D1.codigo());
        assertEquals(86_400_000L, Intervalo.D1.milisegundos());
    }

    @Test
    void desdeCodigoEncuentraCadaIntervalo() {
        for (Intervalo intervalo : Intervalo.values()) {
            assertEquals(intervalo, Intervalo.desdeCodigo(intervalo.codigo()));
        }
    }

    @Test
    void desdeCodigoRechazaCodigosDesconocidos() {
        assertThrows(IllegalArgumentException.class, () -> Intervalo.desdeCodigo("2h"));
        assertThrows(IllegalArgumentException.class, () -> Intervalo.desdeCodigo("1D"));
        assertThrows(IllegalArgumentException.class, () -> Intervalo.desdeCodigo(null));
    }
}
