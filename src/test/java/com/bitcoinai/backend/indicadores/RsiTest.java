package com.bitcoinai.backend.indicadores;

import static com.bitcoinai.backend.indicadores.VelasPrueba.assertSerie;
import static com.bitcoinai.backend.indicadores.VelasPrueba.assertTodos;
import static com.bitcoinai.backend.indicadores.VelasPrueba.deCierres;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import org.junit.jupiter.api.Test;

class RsiTest {

    @Test
    void seriePlanaDaCincuenta() {
        ListaDoble<PuntoIndicador> rsi = new Rsi(14).calcular(VelasPrueba.constantes(30, 100));
        assertEquals(16, rsi.tamanio()); // 30 velas − 14
        assertTodos(rsi, 50);
    }

    @Test
    void serieSiempreCrecienteDaCien() {
        ListaDoble<PuntoIndicador> rsi = new Rsi(14).calcular(VelasPrueba.lineales(40, 100, 3));
        assertEquals(26, rsi.tamanio());
        assertTodos(rsi, 100);
    }

    @Test
    void serieSiempreDecrecienteDaCero() {
        assertTodos(new Rsi(5).calcular(VelasPrueba.lineales(20, 100, -2)), 0);
    }

    @Test
    void valoresCalculadosAManoConSuavizadoDeWilder() {
        // cierres 1,2,1,2,3 → cambios +1,−1,+1,+1; periodo 2
        // inicio: ganancia (1+0)/2 = 0,5; pérdida (0+1)/2 = 0,5 → RS 1 → RSI 50
        // +1: ganancia (0,5·1+1)/2 = 0,75; pérdida (0,5·1+0)/2 = 0,25 → RS 3 → RSI 75
        // +1: ganancia (0,75+1)/2 = 0,875; pérdida 0,125 → RS 7 → RSI 87,5
        assertSerie(new Rsi(2).calcular(deCierres(1, 2, 1, 2, 3)), 2, 50, 75, 87.5);
    }

    @Test
    void primerPuntoNecesitaPeriodoMasUnaVela() {
        assertTrue(new Rsi(3).calcular(deCierres(1, 2, 3)).estaVacia());
        assertEquals(1, new Rsi(3).calcular(deCierres(1, 2, 3, 4)).tamanio());
    }

    @Test
    void siempreEntreCeroYCien() {
        ListaDoble<PuntoIndicador> rsi = new Rsi(3).calcular(deCierres(10, 13, 9, 15, 8, 8, 20, 1, 7));
        for (PuntoIndicador p : rsi) {
            assertTrue(p.valor() >= 0 && p.valor() <= 100, "RSI fuera de rango: " + p.valor());
        }
    }

    @Test
    void serieVaciaYDeUnElemento() {
        assertTrue(new Rsi(14).calcular(new ListaDoble<>()).estaVacia());
        assertTrue(new Rsi(14).calcular(deCierres(5)).estaVacia());
        assertTrue(new Rsi(1).calcular(deCierres(5)).estaVacia());
    }

    @Test
    void periodoInvalido() {
        assertThrows(IllegalArgumentException.class, () -> new Rsi(0));
    }
}
