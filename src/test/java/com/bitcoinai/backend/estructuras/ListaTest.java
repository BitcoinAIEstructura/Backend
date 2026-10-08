package com.bitcoinai.backend.estructuras;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Comparator;
import java.util.Iterator;
import java.util.NoSuchElementException;
import org.junit.jupiter.api.Test;

class ListaTest {

    private static Lista<Integer> listaDe(int... valores) {
        Lista<Integer> lista = new Lista<>();
        for (int v : valores) {
            lista.agregar(v);
        }
        return lista;
    }

    private static Object[] aArreglo(Lista<?> lista) {
        Object[] resultado = new Object[lista.tamanio()];
        int i = 0;
        for (Object valor : lista) {
            resultado[i++] = valor;
        }
        return resultado;
    }

    @Test
    void listaNuevaEstaVacia() {
        Lista<Integer> lista = new Lista<>();
        assertTrue(lista.estaVacia());
        assertEquals(0, lista.tamanio());
        assertFalse(lista.iterator().hasNext());
    }

    @Test
    void primeroYUltimoEnListaVaciaLanzanExcepcion() {
        Lista<Integer> lista = new Lista<>();
        assertThrows(EstructuraVaciaException.class, lista::primero);
        assertThrows(EstructuraVaciaException.class, lista::ultimo);
    }

    @Test
    void unSoloElementoEsPrimeroYUltimo() {
        Lista<Integer> lista = listaDe(7);
        assertEquals(1, lista.tamanio());
        assertEquals(7, lista.primero());
        assertEquals(7, lista.ultimo());
        assertEquals(7, lista.obtener(0));
    }

    @Test
    void agregarYAgregarInicioRespetanElOrden() {
        Lista<Integer> lista = new Lista<>();
        lista.agregar(2);
        lista.agregar(3);
        lista.agregarInicio(1);
        lista.agregarInicio(0);
        assertArrayEquals(new Object[] {0, 1, 2, 3}, aArreglo(lista));
        assertEquals(0, lista.primero());
        assertEquals(3, lista.ultimo());
    }

    @Test
    void agregarInicioEnListaVaciaActualizaLaCola() {
        Lista<Integer> lista = new Lista<>();
        lista.agregarInicio(5);
        lista.agregar(6);
        assertEquals(5, lista.primero());
        assertEquals(6, lista.ultimo());
    }

    @Test
    void obtenerConIndiceInvalidoLanzaExcepcion() {
        Lista<Integer> lista = listaDe(1, 2, 3);
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.obtener(-1));
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.obtener(3));
        assertThrows(IndiceFueraDeRangoException.class, () -> new Lista<Integer>().obtener(0));
    }

    @Test
    void eliminarConIndiceInvalidoLanzaExcepcion() {
        Lista<Integer> lista = listaDe(1, 2);
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.eliminar(-1));
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.eliminar(2));
        assertEquals(2, lista.tamanio());
    }

    @Test
    void eliminarCabezaMedioYColaMantieneExtremos() {
        Lista<Integer> lista = listaDe(1, 2, 3, 4, 5);
        assertEquals(1, lista.eliminar(0));
        assertEquals(3, lista.eliminar(1));
        assertEquals(5, lista.eliminar(2));
        assertArrayEquals(new Object[] {2, 4}, aArreglo(lista));
        assertEquals(2, lista.primero());
        assertEquals(4, lista.ultimo());
        lista.agregar(6);
        assertArrayEquals(new Object[] {2, 4, 6}, aArreglo(lista));
    }

    @Test
    void eliminarElUnicoElementoDejaLaListaVaciaYReutilizable() {
        Lista<Integer> lista = listaDe(9);
        assertEquals(9, lista.eliminar(0));
        assertTrue(lista.estaVacia());
        assertThrows(EstructuraVaciaException.class, lista::ultimo);
        lista.agregar(10);
        assertEquals(10, lista.primero());
        assertEquals(10, lista.ultimo());
    }

    @Test
    void insertarOrdenadoDejaLaListaOrdenada() {
        Lista<Integer> lista = new Lista<>();
        for (int v : new int[] {5, 1, 4, 2, 3, 0, 6}) {
            lista.insertarOrdenado(v, Comparator.naturalOrder());
        }
        assertArrayEquals(new Object[] {0, 1, 2, 3, 4, 5, 6}, aArreglo(lista));
        assertEquals(0, lista.primero());
        assertEquals(6, lista.ultimo());
    }

    @Test
    void insertarOrdenadoEsEstableConElementosIguales() {
        Lista<String> lista = new Lista<>();
        Comparator<String> porLargo = Comparator.comparingInt(String::length);
        lista.insertarOrdenado("bb", porLargo);
        lista.insertarOrdenado("a", porLargo);
        lista.insertarOrdenado("cc", porLargo);
        lista.insertarOrdenado("d", porLargo);
        assertArrayEquals(new Object[] {"a", "d", "bb", "cc"}, aArreglo(lista));
    }

    @Test
    void buscarDevuelveElPrimerIndiceOMenosUno() {
        Lista<Integer> lista = listaDe(4, 8, 15, 16, 23, 42);
        assertEquals(2, lista.buscar(v -> v > 10));
        assertEquals(0, lista.buscar(v -> v == 4));
        assertEquals(5, lista.buscar(v -> v == 42));
        assertEquals(-1, lista.buscar(v -> v > 100));
        assertEquals(-1, new Lista<Integer>().buscar(v -> true));
    }

    @Test
    void vaciarDejaLaListaVaciaYReutilizable() {
        Lista<Integer> lista = listaDe(1, 2, 3);
        lista.vaciar();
        assertTrue(lista.estaVacia());
        assertEquals(0, lista.tamanio());
        lista.agregar(4);
        assertArrayEquals(new Object[] {4}, aArreglo(lista));
    }

    @Test
    void iteradorTerminaConNoSuchElementException() {
        Iterator<Integer> it = listaDe(1).iterator();
        assertEquals(1, it.next());
        assertFalse(it.hasNext());
        assertThrows(NoSuchElementException.class, it::next);
    }
}
