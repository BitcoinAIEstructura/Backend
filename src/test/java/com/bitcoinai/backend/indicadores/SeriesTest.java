package com.bitcoinai.backend.indicadores;

import static com.bitcoinai.backend.indicadores.VelasPrueba.assertSerie;
import static com.bitcoinai.backend.indicadores.VelasPrueba.deCierres;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import org.junit.jupiter.api.Test;

class SeriesTest {

    private static ListaDoble<Integer> unoADiez() {
        ListaDoble<Integer> lista = new ListaDoble<>();
        for (int i = 1; i <= 10; i++) {
            lista.agregarFinal(i);
        }
        return lista;
    }

    @Test
    void cierresConvierteVelasEnPuntos() {
        assertSerie(Series.cierres(deCierres(3, 1, 4)), 0, 3, 1, 4);
        assertTrue(Series.cierres(null).estaVacia());
    }

    @Test
    void ultimosDevuelveLosMasRecientesEnOrdenCronologico() {
        ListaDoble<Integer> ultimos = Series.ultimos(unoADiez(), 3);
        assertEquals(3, ultimos.tamanio());
        assertEquals(8, ultimos.primero());
        assertEquals(10, ultimos.ultimo());
        assertEquals(9, ultimos.obtener(1));
    }

    @Test
    void ultimosConMasDeLosQueHayOCero() {
        assertEquals(10, Series.ultimos(unoADiez(), 50).tamanio());
        assertTrue(Series.ultimos(unoADiez(), 0).estaVacia());
        assertTrue(Series.ultimos(new ListaDoble<Integer>(), 3).estaVacia());
        assertThrows(IllegalArgumentException.class, () -> Series.ultimos(unoADiez(), -1));
    }

    @Test
    void ultimosNoModificaLaOriginal() {
        ListaDoble<Integer> original = unoADiez();
        Series.ultimos(original, 4).vaciar();
        assertEquals(10, original.tamanio());
    }

    @Test
    void emaDeUnaSerieDePuntos() {
        assertSerie(Series.ema(Series.cierres(deCierres(1, 2, 3, 4, 5)), 3), 2, 2, 3, 4);
        assertThrows(IllegalArgumentException.class, () -> Series.ema(new ListaDoble<>(), 0));
    }
}
