package com.bitcoinai.backend.indicadores;

import static com.bitcoinai.backend.indicadores.VelasPrueba.assertSerie;
import static com.bitcoinai.backend.indicadores.VelasPrueba.assertTodos;
import static com.bitcoinai.backend.indicadores.VelasPrueba.deCierres;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import java.util.Map;
import org.junit.jupiter.api.Test;

class MacdTest {

    @Test
    void valoresCalculadosAManoConPeriodosPequenos() {
        // cierres 1..6, rápida 2, lenta 3, señal 2
        // EMA2 (α 2/3): 1,5 2,5 3,5 4,5 5,5 (desde la vela 1)
        // EMA3 (α 1/2): 2 3 4 5 (desde la vela 2)
        // MACD = 0,5 en todas desde la vela 2; señal = 0,5 desde la vela 3; histograma 0
        ResultadoMacd r = new Macd(2, 3, 2).calcularCompleto(deCierres(1, 2, 3, 4, 5, 6));
        assertSerie(r.macd(), 2, 0.5, 0.5, 0.5, 0.5);
        assertSerie(r.senal(), 3, 0.5, 0.5, 0.5);
        assertSerie(r.histograma(), 3, 0, 0, 0);
    }

    @Test
    void serieConstanteDaTodoCero() {
        ResultadoMacd r = new Macd().calcularCompleto(VelasPrueba.constantes(60, 100));
        assertEquals(35, r.macd().tamanio());       // 60 − 26 + 1
        assertEquals(27, r.senal().tamanio());      // 35 − 9 + 1
        assertEquals(27, r.histograma().tamanio());
        assertTodos(r.macd(), 0);
        assertTodos(r.senal(), 0);
        assertTodos(r.histograma(), 0);
    }

    @Test
    void tendenciaAlcistaDaMacdPositivo() {
        ResultadoMacd r = new Macd().calcularCompleto(VelasPrueba.lineales(80, 100, 2));
        for (PuntoIndicador p : r.macd()) {
            assertTrue(p.valor() > 0);
        }
    }

    @Test
    void histogramaEsMacdMenosSenalEnElMismoTiempo() {
        ResultadoMacd r = new Macd(3, 6, 3).calcularCompleto(deCierres(5, 7, 6, 9, 12, 10, 8, 11, 15, 14, 13, 16));
        ListaDoble<PuntoIndicador> macdAlineado = Series.ultimos(r.macd(), r.senal().tamanio());
        var itM = macdAlineado.iteradorAdelante();
        var itS = r.senal().iteradorAdelante();
        for (PuntoIndicador h : r.histograma()) {
            PuntoIndicador m = itM.next();
            PuntoIndicador s = itS.next();
            assertEquals(m.tiempo(), h.tiempo());
            assertEquals(s.tiempo(), h.tiempo());
            assertEquals(m.valor() - s.valor(), h.valor(), 1e-12);
        }
    }

    @Test
    void calcularSeriesDevuelveLasTresConNombre() {
        Map<String, ListaDoble<PuntoIndicador>> series = new Macd().calcularSeries(VelasPrueba.lineales(50, 1, 1));
        assertEquals("[macd, senal, histograma]", series.keySet().toString());
        assertEquals(series.get("macd").tamanio(), new Macd().calcular(VelasPrueba.lineales(50, 1, 1)).tamanio());
    }

    @Test
    void pocasVelasDanSeriesVacias() {
        ResultadoMacd r = new Macd().calcularCompleto(deCierres(1, 2, 3));
        assertTrue(r.macd().estaVacia());
        assertTrue(r.senal().estaVacia());
        assertTrue(r.histograma().estaVacia());
        assertTrue(new Macd().calcular(new ListaDoble<>()).estaVacia());
        assertTrue(new Macd(2, 3, 2).calcular(deCierres(5)).estaVacia());
    }

    @Test
    void parametrosInvalidos() {
        assertThrows(IllegalArgumentException.class, () -> new Macd(26, 12, 9));
        assertThrows(IllegalArgumentException.class, () -> new Macd(12, 12, 9));
        assertThrows(IllegalArgumentException.class, () -> new Macd(12, 26, 0));
        assertEquals("{rapido=12, lento=26, senal=9}", new Macd().parametros().toString());
    }
}
