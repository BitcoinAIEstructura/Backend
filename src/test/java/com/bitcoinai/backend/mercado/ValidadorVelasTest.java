package com.bitcoinai.backend.mercado;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import org.junit.jupiter.api.Test;

class ValidadorVelasTest {

    private static Vela vela(long tiempo, double apertura, double maximo, double minimo, double cierre, double volumen) {
        return new Vela(tiempo, apertura, maximo, minimo, cierre, volumen, tiempo + 59_999);
    }

    private static ListaDoble<Vela> listaDe(Vela... velas) {
        ListaDoble<Vela> lista = new ListaDoble<>();
        for (Vela v : velas) {
            lista.agregarFinal(v);
        }
        return lista;
    }

    private static void assertInvalida(String fragmento, Vela... velas) {
        MercadoException e = assertThrows(MercadoException.class, () -> ValidadorVelas.validar(listaDe(velas)));
        assertTrue(e.getMessage().contains(fragmento), "mensaje: " + e.getMessage());
    }

    @Test
    void serieValidaPasa() {
        assertDoesNotThrow(() -> ValidadorVelas.validar(FuenteFalsa.generarVelas(100, Intervalo.M1)));
    }

    @Test
    void serieVaciaYDeUnaVelaPasan() {
        assertDoesNotThrow(() -> ValidadorVelas.validar(new ListaDoble<>()));
        assertDoesNotThrow(() -> ValidadorVelas.validar(listaDe(vela(0, 10, 12, 9, 11, 0))));
    }

    @Test
    void velasDesordenadasFallanConLaPosicion() {
        assertInvalida("posición 2: velas desordenadas",
                vela(0, 10, 12, 9, 11, 1), vela(120_000, 10, 12, 9, 11, 1), vela(60_000, 10, 12, 9, 11, 1));
    }

    @Test
    void velasDuplicadasFallan() {
        assertInvalida("posición 1: vela duplicada", vela(0, 10, 12, 9, 11, 1), vela(0, 10, 12, 9, 11, 1));
    }

    @Test
    void preciosCeroNegativosONoFinitosFallan() {
        assertInvalida("positivos", vela(0, 0, 12, 9, 11, 1));
        assertInvalida("positivos", vela(0, 10, 12, -9, 11, 1));
        assertInvalida("positivos", vela(0, 10, Double.NaN, 9, 11, 1));
        assertInvalida("positivos", vela(0, 10, Double.POSITIVE_INFINITY, 9, 11, 1));
    }

    @Test
    void maximoMenorQueMinimoFalla() {
        assertInvalida("máximo es menor que el mínimo", vela(0, 10, 9, 12, 11, 1));
    }

    @Test
    void aperturaOCierreFueraDelRangoFallan() {
        assertInvalida("fuera del rango", vela(0, 13, 12, 9, 11, 1));
        assertInvalida("fuera del rango", vela(0, 10, 12, 9, 8, 1));
    }

    @Test
    void volumenNegativoFalla() {
        assertInvalida("volumen", vela(0, 10, 12, 9, 11, -1));
    }

    @Test
    void tiempoDeCierreAnteriorALaAperturaFalla() {
        assertInvalida("tiempo de cierre", new Vela(1000, 10, 12, 9, 11, 1, 999));
    }

    @Test
    void velaNulaFalla() {
        ListaDoble<Vela> lista = new ListaDoble<>();
        lista.agregarFinal(null);
        assertThrows(MercadoException.class, () -> ValidadorVelas.validar(lista));
    }
}
