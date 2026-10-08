package com.bitcoinai.backend.indicadores;

import static com.bitcoinai.backend.indicadores.VelasPrueba.assertSerie;
import static com.bitcoinai.backend.indicadores.VelasPrueba.assertTodos;
import static com.bitcoinai.backend.indicadores.VelasPrueba.deCierres;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Iterator;
import org.junit.jupiter.api.Test;

class BollingerYVolatilidadTest {

    // ---------- Bollinger ----------

    @Test
    void serieConstanteTieneBandasIgualesALaMedia() {
        ResultadoBollinger b = new BandasBollinger(20, 2).calcularBandas(VelasPrueba.constantes(30, 85_000.5));
        assertEquals(11, b.media().tamanio());
        assertTodos(b.media(), 85_000.5);
        assertTodos(b.superior(), 85_000.5);
        assertTodos(b.inferior(), 85_000.5);
    }

    @Test
    void valoresCalculadosAMano() {
        // periodo 2, k 2, cierres 1,3,5
        // [1,3]: media 2, σ = 1 → 4 y 0;  [3,5]: media 4, σ = 1 → 6 y 2
        ResultadoBollinger b = new BandasBollinger(2, 2).calcularBandas(deCierres(1, 3, 5));
        assertSerie(b.media(), 1, 2, 4);
        assertSerie(b.superior(), 1, 4, 6);
        assertSerie(b.inferior(), 1, 0, 2);
    }

    @Test
    void mediaCoincideConLaSmaYLasBandasSonSimetricas() {
        ListaDoble<Vela> velas = deCierres(85_010, 84_950, 85_200, 84_700, 85_500, 85_100, 84_900, 85_300);
        ResultadoBollinger b = new BandasBollinger(4, 2).calcularBandas(velas);
        Iterator<PuntoIndicador> sma = new Sma(4).calcular(velas).iteradorAdelante();
        Iterator<PuntoIndicador> sup = b.superior().iteradorAdelante();
        Iterator<PuntoIndicador> inf = b.inferior().iteradorAdelante();
        for (PuntoIndicador media : b.media()) {
            assertEquals(sma.next().valor(), media.valor(), 1e-6);
            double arriba = sup.next().valor() - media.valor();
            double abajo = media.valor() - inf.next().valor();
            assertEquals(arriba, abajo, 1e-6);
            assertTrue(arriba > 0);
        }
    }

    @Test
    void bollingerConSerieVaciaYUnElemento() {
        assertTrue(new BandasBollinger(20, 2).calcular(new ListaDoble<>()).estaVacia());
        assertTrue(new BandasBollinger(2, 2).calcular(deCierres(5)).estaVacia());
        assertSerie(new BandasBollinger(1, 2).calcularBandas(deCierres(5)).superior(), 0, 5);
        assertEquals("[media, superior, inferior]",
                new BandasBollinger(2, 2).calcularSeries(deCierres(1, 2)).keySet().toString());
    }

    @Test
    void bollingerParametrosInvalidos() {
        assertThrows(IllegalArgumentException.class, () -> new BandasBollinger(0, 2));
        assertThrows(IllegalArgumentException.class, () -> new BandasBollinger(20, 0));
        assertThrows(IllegalArgumentException.class, () -> new BandasBollinger(20, Double.NaN));
    }

    // ---------- Volatilidad ----------

    @Test
    void preciosConstantesTienenVolatilidadCero() {
        ListaDoble<PuntoIndicador> v = new Volatilidad(5).calcular(VelasPrueba.constantes(10, 100));
        assertEquals(5, v.tamanio());
        assertTodos(v, 0);
    }

    @Test
    void volatilidadCalculadaAMano() {
        // cierres 1, e, e³ → retornos ln(e) = 1 y ln(e²) = 2
        // media 1,5; desviación muestral √(((1−1,5)² + (2−1,5)²) / 1) = √0,5
        assertSerie(new Volatilidad(2).calcular(deCierres(1, Math.E, Math.exp(3))), 2, Math.sqrt(0.5));
    }

    @Test
    void crecimientoPorcentualConstanteTieneVolatilidadCero() {
        // cada cierre es 1 % mayor que el anterior → todos los retornos iguales
        double[] cierres = new double[15];
        cierres[0] = 100;
        for (int i = 1; i < cierres.length; i++) {
            cierres[i] = cierres[i - 1] * 1.01;
        }
        ListaDoble<PuntoIndicador> v = new Volatilidad(5).calcular(deCierres(cierres));
        for (PuntoIndicador p : v) {
            assertEquals(0, p.valor(), 1e-9);
        }
    }

    @Test
    void volatilidadConSerieVaciaUnElementoYPocasVelas() {
        assertTrue(new Volatilidad(3).calcular(new ListaDoble<>()).estaVacia());
        assertTrue(new Volatilidad(3).calcular(deCierres(5)).estaVacia());
        assertTrue(new Volatilidad(3).calcular(deCierres(1, 2, 3)).estaVacia());
        assertEquals(1, new Volatilidad(3).calcular(deCierres(1, 2, 3, 4)).tamanio());
        assertThrows(IllegalArgumentException.class, () -> new Volatilidad(1));
    }
}
