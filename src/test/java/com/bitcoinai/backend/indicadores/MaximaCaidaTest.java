package com.bitcoinai.backend.indicadores;

import static com.bitcoinai.backend.indicadores.VelasPrueba.PASO;
import static com.bitcoinai.backend.indicadores.VelasPrueba.deCierres;
import static org.junit.jupiter.api.Assertions.assertEquals;

import com.bitcoinai.backend.estructuras.ListaDoble;
import org.junit.jupiter.api.Test;

class MaximaCaidaTest {

    @Test
    void encuentraLaPeorCaidaAunqueHayaOtrasDespues() {
        // 120 → 90 es −25 %; luego 130 → 104 es −20 %
        ResultadoCaida r = MaximaCaida.deVelas(deCierres(100, 120, 90, 130, 104));
        assertEquals(0.25, r.caidaMaxima(), 1e-12);
        assertEquals(120, r.valorPico());
        assertEquals(PASO, r.tiempoPico());
        assertEquals(90, r.valorValle());
        assertEquals(2 * PASO, r.tiempoValle());
    }

    @Test
    void caidaQueSigueBajandoTomaElPuntoMasBajo() {
        ResultadoCaida r = MaximaCaida.deVelas(deCierres(100, 80, 60, 70, 50, 90));
        assertEquals(0.5, r.caidaMaxima(), 1e-12);
        assertEquals(100, r.valorPico());
        assertEquals(50, r.valorValle());
    }

    @Test
    void serieQueSoloSubeNoTieneCaida() {
        ResultadoCaida r = MaximaCaida.deVelas(VelasPrueba.lineales(10, 1, 1));
        assertEquals(0, r.caidaMaxima());
        assertEquals(1, r.valorPico());
        assertEquals(1, r.valorValle());
    }

    @Test
    void serieVaciaYDeUnElemento() {
        assertEquals(new ResultadoCaida(0, 0, 0, 0, 0), MaximaCaida.deVelas(new ListaDoble<>()));
        assertEquals(new ResultadoCaida(0, 0, 0, 0, 0), MaximaCaida.dePuntos(null));
        assertEquals(new ResultadoCaida(0, 0, 7, 0, 7), MaximaCaida.deVelas(deCierres(7)));
    }

    @Test
    void funcionaConPuntosDeCapital() {
        ListaDoble<PuntoIndicador> capital = new ListaDoble<>();
        capital.agregarFinal(new PuntoIndicador(1, 1000));
        capital.agregarFinal(new PuntoIndicador(2, 900));
        capital.agregarFinal(new PuntoIndicador(3, 1100));
        assertEquals(0.1, MaximaCaida.dePuntos(capital).caidaMaxima(), 1e-12);
    }
}
