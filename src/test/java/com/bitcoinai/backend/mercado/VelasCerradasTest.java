package com.bitcoinai.backend.mercado;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import org.junit.jupiter.api.Test;

class VelasCerradasTest {

    @Test
    void quitaSoloLasVelasQueNoHanCerrado() {
        ListaDoble<Vela> velas = FuenteFalsa.generarVelas(5, Intervalo.D1);
        long cierreDeLaCuarta = velas.obtener(3).tiempoCierre();
        // "ahora" es justo el cierre de la cuarta: la cuarta y la quinta todavía no cerraron
        VelasCerradas.filtrar(velas, cierreDeLaCuarta);
        assertEquals(3, velas.tamanio());
        // "ahora" antes de todo: ninguna vela cerró todavía
        VelasCerradas.filtrar(velas, 0);
        assertTrue(velas.estaVacia());
    }

    @Test
    void siTodasCerraronNoCambiaNada() {
        ListaDoble<Vela> velas = FuenteFalsa.generarVelas(5, Intervalo.D1);
        assertEquals(5, VelasCerradas.filtrar(velas, velas.ultimo().tiempoCierre() + 1).tamanio());
        assertEquals(0, VelasCerradas.filtrar(new ListaDoble<>(), 0).tamanio());
    }
}
