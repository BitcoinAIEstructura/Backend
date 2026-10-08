package com.bitcoinai.backend.estructuras;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;

import org.junit.jupiter.api.Test;

class NodosTest {

    @Test
    void nodoSimpleNuevoNoTieneSiguiente() {
        NodoSimple<String> nodo = new NodoSimple<>("a");
        assertEquals("a", nodo.getValor());
        assertNull(nodo.getSiguiente());
    }

    @Test
    void nodoSimpleSePuedeEnlazar() {
        NodoSimple<String> segundo = new NodoSimple<>("b");
        NodoSimple<String> primero = new NodoSimple<>("a", segundo);
        assertSame(segundo, primero.getSiguiente());

        NodoSimple<String> tercero = new NodoSimple<>("c");
        segundo.setSiguiente(tercero);
        assertSame(tercero, primero.getSiguiente().getSiguiente());
    }

    @Test
    void nodoSimpleAceptaValorNulo() {
        assertNull(new NodoSimple<String>(null).getValor());
    }

    @Test
    void nodoDobleNuevoNoTieneVecinos() {
        NodoDoble<Integer> nodo = new NodoDoble<>(1);
        assertEquals(1, nodo.getValor());
        assertNull(nodo.getAnterior());
        assertNull(nodo.getSiguiente());
    }

    @Test
    void nodoDobleSeEnlazaEnAmbosSentidos() {
        NodoDoble<Integer> a = new NodoDoble<>(1);
        NodoDoble<Integer> b = new NodoDoble<>(2);
        a.setSiguiente(b);
        b.setAnterior(a);
        assertSame(b, a.getSiguiente());
        assertSame(a, b.getAnterior());
        assertSame(a, a.getSiguiente().getAnterior());
    }
}
