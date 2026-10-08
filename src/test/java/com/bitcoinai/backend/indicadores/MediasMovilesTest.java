package com.bitcoinai.backend.indicadores;

import static com.bitcoinai.backend.indicadores.VelasPrueba.assertSerie;
import static com.bitcoinai.backend.indicadores.VelasPrueba.deCierres;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import org.junit.jupiter.api.Test;

/** Pruebas de SMA y EMA. */
class MediasMovilesTest {

    // ---------- SMA ----------

    @Test
    void smaDeUnoACincoConPeriodoTres() {
        // (1+2+3)/3 = 2, (2+3+4)/3 = 3, (3+4+5)/3 = 4; el primer punto es la vela 2
        assertSerie(new Sma(3).calcular(deCierres(1, 2, 3, 4, 5)), 2, 2, 3, 4);
    }

    @Test
    void smaConPeriodoUnoEsElPrecio() {
        assertSerie(new Sma(1).calcular(deCierres(7, 3, 9)), 0, 7, 3, 9);
    }

    @Test
    void smaConVentanaDeslizanteLarga() {
        // 1..10 con periodo 4: medias 2.5, 3.5, ..., 8.5
        assertSerie(new Sma(4).calcular(VelasPrueba.lineales(10, 1, 1)), 3, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5);
    }

    @Test
    void smaConSerieVaciaUnElementoOPeriodoMayor() {
        assertTrue(new Sma(3).calcular(new ListaDoble<>()).estaVacia());
        assertTrue(new Sma(3).calcular(null).estaVacia());
        assertTrue(new Sma(2).calcular(deCierres(5)).estaVacia());
        assertSerie(new Sma(1).calcular(deCierres(5)), 0, 5);
        assertTrue(new Sma(10).calcular(deCierres(1, 2, 3)).estaVacia());
    }

    @Test
    void smaNoModificaLasVelasDeEntrada() {
        ListaDoble<Vela> velas = deCierres(1, 2, 3, 4);
        new Sma(2).calcular(velas);
        assertEquals(4, velas.tamanio());
    }

    // ---------- EMA ----------

    @Test
    void emaConPeriodoUnoEsIgualAlPrecio() {
        assertSerie(new Ema(1).calcular(deCierres(10, 12, 11, 15, 14)), 0, 10, 12, 11, 15, 14);
    }

    @Test
    void emaSeInicializaConLaSmaYLuegoSuaviza() {
        // α = 2/(3+1) = 0,5; EMA₀ = (1+2+3)/3 = 2; luego 0,5·4 + 0,5·2 = 3; 0,5·5 + 0,5·3 = 4
        assertSerie(new Ema(3).calcular(deCierres(1, 2, 3, 4, 5)), 2, 2, 3, 4);
    }

    @Test
    void emaConPeriodoDos() {
        // α = 2/3; EMA₀ = (2+4)/2 = 3; 2/3·6 + 1/3·3 = 5; 2/3·8 + 1/3·5 = 7; luego 9 y 11
        assertSerie(new Ema(2).calcular(deCierres(2, 4, 6, 8, 10, 12)), 1, 3, 5, 7, 9, 11);
    }

    @Test
    void emaReaccionaMasRapidoQueLaSma() {
        ListaDoble<Vela> velas = deCierres(10, 10, 10, 10, 20);
        double ema = new Ema(4).calcular(velas).ultimo().valor();
        double sma = new Sma(4).calcular(velas).ultimo().valor();
        assertEquals(14.0, ema, 1e-9); // 0,4·20 + 0,6·10
        assertEquals(12.5, sma, 1e-9);
    }

    @Test
    void emaConSerieVaciaYUnElemento() {
        assertTrue(new Ema(3).calcular(new ListaDoble<>()).estaVacia());
        assertTrue(new Ema(3).calcular(deCierres(5)).estaVacia());
        assertSerie(new Ema(1).calcular(deCierres(5)), 0, 5);
    }

    @Test
    void periodosInvalidosEnElConstructor() {
        assertThrows(IllegalArgumentException.class, () -> new Sma(0));
        assertThrows(IllegalArgumentException.class, () -> new Ema(-1));
    }
}
