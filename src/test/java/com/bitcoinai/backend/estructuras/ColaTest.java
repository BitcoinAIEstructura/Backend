package com.bitcoinai.backend.estructuras;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class ColaTest {

    @Test
    void colaNuevaEstaVacia() {
        Cola<String> cola = new Cola<>();
        assertTrue(cola.estaVacia());
        assertEquals(0, cola.tamanio());
    }

    @Test
    void desencolarYVerFrenteEnColaVaciaLanzanExcepcion() {
        Cola<String> cola = new Cola<>();
        assertThrows(EstructuraVaciaException.class, cola::desencolar);
        assertThrows(EstructuraVaciaException.class, cola::verFrente);
    }

    @Test
    void unSoloElemento() {
        Cola<String> cola = new Cola<>();
        cola.encolar("a");
        assertFalse(cola.estaVacia());
        assertEquals(1, cola.tamanio());
        assertEquals("a", cola.verFrente());
        assertEquals("a", cola.desencolar());
        assertTrue(cola.estaVacia());
    }

    @Test
    void respetaElOrdenFifo() {
        Cola<Integer> cola = new Cola<>();
        for (int i = 1; i <= 5; i++) {
            cola.encolar(i);
        }
        for (int i = 1; i <= 5; i++) {
            assertEquals(i, cola.desencolar());
        }
        assertTrue(cola.estaVacia());
    }

    @Test
    void verFrenteNoQuitaElElemento() {
        Cola<Integer> cola = new Cola<>();
        cola.encolar(1);
        cola.encolar(2);
        assertEquals(1, cola.verFrente());
        assertEquals(1, cola.verFrente());
        assertEquals(2, cola.tamanio());
    }

    @Test
    void encolarYDesencolarIntercaladosMantienenElOrden() {
        Cola<Integer> cola = new Cola<>();
        cola.encolar(1);
        cola.encolar(2);
        assertEquals(1, cola.desencolar());
        cola.encolar(3);
        assertEquals(2, cola.desencolar());
        cola.encolar(4);
        assertEquals(3, cola.desencolar());
        assertEquals(4, cola.desencolar());
        assertTrue(cola.estaVacia());
    }

    @Test
    void sePuedeReutilizarDespuesDeQuedarVaciaAlDesencolar() {
        Cola<Integer> cola = new Cola<>();
        cola.encolar(1);
        cola.desencolar();
        assertThrows(EstructuraVaciaException.class, cola::verFrente);
        cola.encolar(2);
        cola.encolar(3);
        assertEquals(2, cola.desencolar());
        assertEquals(3, cola.desencolar());
    }

    @Test
    void vaciarQuitaTodoYPermiteReutilizar() {
        Cola<Integer> cola = new Cola<>();
        cola.encolar(1);
        cola.encolar(2);
        cola.vaciar();
        assertTrue(cola.estaVacia());
        assertThrows(EstructuraVaciaException.class, cola::desencolar);
        cola.encolar(3);
        assertEquals(3, cola.verFrente());
        assertEquals(1, cola.tamanio());
    }

    @Test
    void tamanioCorrectoConMuchosElementos() {
        Cola<Integer> cola = new Cola<>();
        for (int i = 0; i < 10_000; i++) {
            cola.encolar(i);
        }
        assertEquals(10_000, cola.tamanio());
        for (int i = 0; i < 9_999; i++) {
            cola.desencolar();
        }
        assertEquals(1, cola.tamanio());
        assertEquals(9_999, cola.verFrente());
    }
}
