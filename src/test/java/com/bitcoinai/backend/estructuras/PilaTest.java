package com.bitcoinai.backend.estructuras;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class PilaTest {

    @Test
    void pilaNuevaEstaVacia() {
        Pila<String> pila = new Pila<>();
        assertTrue(pila.estaVacia());
        assertEquals(0, pila.tamanio());
    }

    @Test
    void desapilarYVerTopeEnPilaVaciaLanzanExcepcion() {
        Pila<String> pila = new Pila<>();
        assertThrows(EstructuraVaciaException.class, pila::desapilar);
        assertThrows(EstructuraVaciaException.class, pila::verTope);
    }

    @Test
    void unSoloElemento() {
        Pila<String> pila = new Pila<>();
        pila.apilar("a");
        assertFalse(pila.estaVacia());
        assertEquals(1, pila.tamanio());
        assertEquals("a", pila.verTope());
        assertEquals("a", pila.desapilar());
        assertTrue(pila.estaVacia());
    }

    @Test
    void respetaElOrdenLifo() {
        Pila<Integer> pila = new Pila<>();
        for (int i = 1; i <= 5; i++) {
            pila.apilar(i);
        }
        for (int i = 5; i >= 1; i--) {
            assertEquals(i, pila.desapilar());
        }
        assertTrue(pila.estaVacia());
    }

    @Test
    void verTopeNoQuitaElElemento() {
        Pila<Integer> pila = new Pila<>();
        pila.apilar(1);
        pila.apilar(2);
        assertEquals(2, pila.verTope());
        assertEquals(2, pila.verTope());
        assertEquals(2, pila.tamanio());
    }

    @Test
    void apilarYDesapilarIntercalados() {
        Pila<Integer> pila = new Pila<>();
        pila.apilar(1);
        pila.apilar(2);
        assertEquals(2, pila.desapilar());
        pila.apilar(3);
        assertEquals(3, pila.desapilar());
        assertEquals(1, pila.desapilar());
        assertTrue(pila.estaVacia());
    }

    @Test
    void sePuedeReutilizarDespuesDeQuedarVacia() {
        Pila<Integer> pila = new Pila<>();
        pila.apilar(1);
        pila.desapilar();
        assertThrows(EstructuraVaciaException.class, pila::verTope);
        pila.apilar(2);
        assertEquals(2, pila.verTope());
        assertEquals(1, pila.tamanio());
    }

    @Test
    void vaciarQuitaTodo() {
        Pila<Integer> pila = new Pila<>();
        pila.apilar(1);
        pila.apilar(2);
        pila.vaciar();
        assertTrue(pila.estaVacia());
        assertEquals(0, pila.tamanio());
        assertThrows(EstructuraVaciaException.class, pila::desapilar);
    }

    @Test
    void tamanioCorrectoConMuchosElementos() {
        Pila<Integer> pila = new Pila<>();
        for (int i = 0; i < 10_000; i++) {
            pila.apilar(i);
        }
        assertEquals(10_000, pila.tamanio());
        assertEquals(9_999, pila.verTope());
        for (int i = 0; i < 9_999; i++) {
            pila.desapilar();
        }
        assertEquals(0, pila.verTope());
    }
}
