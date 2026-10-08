package com.bitcoinai.backend.estructuras;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Iterator;
import java.util.NoSuchElementException;
import org.junit.jupiter.api.Test;

class ListaDobleTest {

    private static ListaDoble<Integer> listaDe(int... valores) {
        ListaDoble<Integer> lista = new ListaDoble<>();
        for (int v : valores) {
            lista.agregarFinal(v);
        }
        return lista;
    }

    private static Object[] adelante(ListaDoble<?> lista) {
        return recorrer(lista.iteradorAdelante(), lista.tamanio());
    }

    private static Object[] atras(ListaDoble<?> lista) {
        return recorrer(lista.iteradorAtras(), lista.tamanio());
    }

    private static Object[] recorrer(Iterator<?> it, int tamanio) {
        Object[] resultado = new Object[tamanio];
        int i = 0;
        while (it.hasNext()) {
            resultado[i++] = it.next();
        }
        assertEquals(tamanio, i, "el iterador debe recorrer exactamente tamanio() elementos");
        return resultado;
    }

    private static Object[] invertir(Object[] arreglo) {
        Object[] invertido = new Object[arreglo.length];
        for (int i = 0; i < arreglo.length; i++) {
            invertido[i] = arreglo[arreglo.length - 1 - i];
        }
        return invertido;
    }

    @Test
    void listaNuevaEstaVacia() {
        ListaDoble<Integer> lista = new ListaDoble<>();
        assertTrue(lista.estaVacia());
        assertEquals(0, lista.tamanio());
        assertFalse(lista.iteradorAdelante().hasNext());
        assertFalse(lista.iteradorAtras().hasNext());
    }

    @Test
    void operacionesSobreListaVaciaLanzanExcepcion() {
        ListaDoble<Integer> lista = new ListaDoble<>();
        assertThrows(EstructuraVaciaException.class, lista::eliminarPrimero);
        assertThrows(EstructuraVaciaException.class, lista::eliminarUltimo);
        assertThrows(EstructuraVaciaException.class, lista::primero);
        assertThrows(EstructuraVaciaException.class, lista::ultimo);
        assertThrows(NoSuchElementException.class, () -> lista.iteradorAtras().next());
    }

    @Test
    void unSoloElementoSeQuitaPorCualquierExtremo() {
        ListaDoble<Integer> lista = listaDe(1);
        assertEquals(1, lista.primero());
        assertEquals(1, lista.ultimo());
        assertEquals(1, lista.eliminarUltimo());
        assertTrue(lista.estaVacia());
        assertThrows(EstructuraVaciaException.class, lista::primero);

        lista.agregarInicio(2);
        assertEquals(2, lista.eliminarPrimero());
        assertTrue(lista.estaVacia());
        assertThrows(EstructuraVaciaException.class, lista::ultimo);
    }

    @Test
    void agregarEnAmbosExtremosRespetaElOrden() {
        ListaDoble<Integer> lista = new ListaDoble<>();
        lista.agregarFinal(2);
        lista.agregarInicio(1);
        lista.agregarFinal(3);
        lista.agregarInicio(0);
        assertArrayEquals(new Object[] {0, 1, 2, 3}, adelante(lista));
        assertEquals(0, lista.primero());
        assertEquals(3, lista.ultimo());
    }

    @Test
    void insertarAlInicioEnMedioYAlFinal() {
        ListaDoble<Integer> lista = listaDe(1, 3);
        lista.insertar(1, 2);
        lista.insertar(0, 0);
        lista.insertar(4, 4);
        assertArrayEquals(new Object[] {0, 1, 2, 3, 4}, adelante(lista));
        assertArrayEquals(new Object[] {4, 3, 2, 1, 0}, atras(lista));
    }

    @Test
    void insertarConIndiceInvalidoLanzaExcepcion() {
        ListaDoble<Integer> lista = listaDe(1, 2);
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.insertar(-1, 9));
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.insertar(3, 9));
        assertEquals(2, lista.tamanio());
    }

    @Test
    void obtenerDevuelveCadaPosicionDesdeAmbosExtremos() {
        ListaDoble<Integer> par = listaDe(0, 1, 2, 3, 4, 5, 6, 7, 8, 9);
        for (int i = 0; i < par.tamanio(); i++) {
            assertEquals(i, par.obtener(i));
        }
        ListaDoble<Integer> impar = listaDe(0, 1, 2, 3, 4);
        for (int i = 0; i < impar.tamanio(); i++) {
            assertEquals(i, impar.obtener(i));
        }
    }

    @Test
    void obtenerYEliminarConIndiceInvalidoLanzanExcepcion() {
        ListaDoble<Integer> lista = listaDe(1, 2, 3);
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.obtener(-1));
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.obtener(3));
        assertThrows(IndiceFueraDeRangoException.class, () -> lista.eliminar(3));
        assertThrows(IndiceFueraDeRangoException.class, () -> new ListaDoble<Integer>().obtener(0));
    }

    @Test
    void eliminarPorIndiceEnExtremosYEnMedio() {
        ListaDoble<Integer> lista = listaDe(0, 1, 2, 3, 4, 5);
        assertEquals(3, lista.eliminar(3));
        assertEquals(0, lista.eliminar(0));
        assertEquals(5, lista.eliminar(lista.tamanio() - 1));
        assertArrayEquals(new Object[] {1, 2, 4}, adelante(lista));
        assertEquals(1, lista.primero());
        assertEquals(4, lista.ultimo());
    }

    @Test
    void conservarUltimosDescartaLosMasAntiguos() {
        ListaDoble<Integer> lista = listaDe(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
        lista.conservarUltimos(3);
        assertArrayEquals(new Object[] {8, 9, 10}, adelante(lista));

        lista.conservarUltimos(5);
        assertEquals(3, lista.tamanio());

        lista.agregarFinal(11);
        lista.conservarUltimos(3);
        assertArrayEquals(new Object[] {9, 10, 11}, adelante(lista));
        assertArrayEquals(new Object[] {11, 10, 9}, atras(lista));

        lista.conservarUltimos(0);
        assertTrue(lista.estaVacia());
        assertThrows(IllegalArgumentException.class, () -> lista.conservarUltimos(-1));
    }

    @Test
    void recorridoAtrasEsElInversoDelRecorridoAdelanteTrasVariasOperaciones() {
        ListaDoble<Integer> lista = new ListaDoble<>();
        for (int i = 0; i < 20; i++) {
            if (i % 2 == 0) {
                lista.agregarFinal(i);
            } else {
                lista.agregarInicio(i);
            }
        }
        lista.insertar(5, 100);
        lista.insertar(15, 200);
        lista.eliminarPrimero();
        lista.eliminarUltimo();
        lista.eliminar(7);
        lista.eliminar(12);
        lista.conservarUltimos(14);
        lista.agregarFinal(300);
        lista.insertar(0, 400);

        Object[] haciaAdelante = adelante(lista);
        assertArrayEquals(invertir(haciaAdelante), atras(lista));
        assertEquals(16, lista.tamanio());
        assertEquals(400, lista.primero());
        assertEquals(300, lista.ultimo());
    }

    @Test
    void vaciarDejaLaListaVaciaYReutilizable() {
        ListaDoble<Integer> lista = listaDe(1, 2, 3);
        lista.vaciar();
        assertTrue(lista.estaVacia());
        assertFalse(lista.iteradorAtras().hasNext());
        lista.agregarInicio(4);
        lista.agregarFinal(5);
        assertArrayEquals(new Object[] {4, 5}, adelante(lista));
        assertArrayEquals(new Object[] {5, 4}, atras(lista));
    }

    @Test
    void eliminarNodoQuitaDelMedioYDeLosExtremosSinRecorrer() {
        ListaDoble<String> lista = new ListaDoble<>();
        NodoDoble<String> a = lista.agregarFinalNodo("a");
        NodoDoble<String> b = lista.agregarFinalNodo("b");
        NodoDoble<String> c = lista.agregarFinalNodo("c");
        NodoDoble<String> d = lista.agregarFinalNodo("d");
        assertEquals("b", b.getValor());

        assertTrue(lista.eliminarNodo(b));          // del medio
        assertArrayEquals(new Object[] {"a", "c", "d"}, adelante(lista));
        assertTrue(lista.eliminarNodo(a));          // la cabeza
        assertTrue(lista.eliminarNodo(d));          // la cola
        assertArrayEquals(new Object[] {"c"}, adelante(lista));
        assertArrayEquals(new Object[] {"c"}, atras(lista));
        assertEquals("c", lista.primero());
        assertEquals("c", lista.ultimo());
        assertTrue(lista.eliminarNodo(c));
        assertTrue(lista.estaVacia());
    }

    @Test
    void eliminarNodoDosVecesODeOtraListaEsSeguro() {
        ListaDoble<Integer> lista = listaDe(1, 2);
        ListaDoble<Integer> otra = new ListaDoble<>();
        NodoDoble<Integer> nodo = lista.agregarFinalNodo(3);
        NodoDoble<Integer> ajeno = otra.agregarFinalNodo(9);

        assertTrue(lista.eliminarNodo(nodo));
        assertFalse(lista.eliminarNodo(nodo));      // ya se había quitado
        assertFalse(lista.eliminarNodo(ajeno));     // es de otra lista
        assertFalse(lista.eliminarNodo(null));
        assertFalse(lista.eliminarNodo(new NodoDoble<>(5)));
        assertArrayEquals(new Object[] {1, 2}, adelante(lista));
        assertEquals(1, otra.tamanio());
    }

    @Test
    void trasVaciarLosNodosViejosQuedanInvalidos() {
        ListaDoble<Integer> lista = new ListaDoble<>();
        NodoDoble<Integer> viejo = lista.agregarFinalNodo(1);
        lista.vaciar();
        lista.agregarFinal(2);
        assertFalse(lista.eliminarNodo(viejo));
        assertEquals(1, lista.tamanio());
        // Un nodo quitado con eliminarPrimero también deja de pertenecer.
        NodoDoble<Integer> primero = lista.agregarFinalNodo(3);
        lista.eliminarUltimo();
        assertFalse(lista.eliminarNodo(primero));
        assertArrayEquals(new Object[] {2}, adelante(lista));
    }

    @Test
    void forEachRecorreHaciaAdelante() {
        ListaDoble<Integer> lista = listaDe(3, 1, 2);
        StringBuilder sb = new StringBuilder();
        for (int v : lista) {
            sb.append(v);
        }
        assertEquals("312", sb.toString());
    }
}
