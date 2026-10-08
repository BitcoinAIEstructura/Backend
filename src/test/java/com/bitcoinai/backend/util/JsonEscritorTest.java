package com.bitcoinai.backend.util;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

class JsonEscritorTest {

    private record Punto(String nombre, double x, Lista<Integer> etiquetas) {
    }

    @Test
    void escribeValoresSimples() {
        assertEquals("null", JsonEscritor.escribir(null));
        assertEquals("true", JsonEscritor.escribir(true));
        assertEquals("false", JsonEscritor.escribir(false));
        assertEquals("\"hola\"", JsonEscritor.escribir("hola"));
        assertEquals("\"c\"", JsonEscritor.escribir('c'));
    }

    @Test
    void escribeNumeros() {
        assertEquals("42", JsonEscritor.escribir(42));
        assertEquals("-9000000000", JsonEscritor.escribir(-9_000_000_000L));
        assertEquals("2.5", JsonEscritor.escribir(2.5));
        assertEquals("3", JsonEscritor.escribir(3.0));
        assertEquals("-0.001", JsonEscritor.escribir(-0.001));
        assertEquals("1.0E20", JsonEscritor.escribir(1e20));
        assertEquals("0.5", JsonEscritor.escribir(0.5f));
    }

    @Test
    void rechazaNaNEInfinito() {
        assertThrows(IllegalArgumentException.class, () -> JsonEscritor.escribir(Double.NaN));
        assertThrows(IllegalArgumentException.class, () -> JsonEscritor.escribir(Double.NEGATIVE_INFINITY));
    }

    @Test
    void escapaCaracteresEspeciales() {
        String texto = "a\"b\\c/\n\r\t\b\f" + (char) 1 + "é";
        assertEquals("\"a\\\"b\\\\c/\\n\\r\\t\\b\\f\\u0001é\"", JsonEscritor.escribir(texto));
    }

    @Test
    void escribeMapasEnOrdenYAnidados() {
        Map<String, Object> interno = new LinkedHashMap<>();
        interno.put("ok", true);
        Map<String, Object> mapa = new LinkedHashMap<>();
        mapa.put("b", 1);
        mapa.put("a", "x");
        mapa.put("n", null);
        mapa.put("interno", interno);
        assertEquals("{\"b\":1,\"a\":\"x\",\"n\":null,\"interno\":{\"ok\":true}}", JsonEscritor.escribir(mapa));
        assertEquals("{}", JsonEscritor.escribir(new LinkedHashMap<>()));
    }

    @Test
    void escribeListaYListaDobleComoArreglos() {
        Lista<Object> lista = new Lista<>();
        lista.agregar(1);
        lista.agregar("dos");
        lista.agregar(new Lista<>());
        assertEquals("[1,\"dos\",[]]", JsonEscritor.escribir(lista));

        ListaDoble<Double> doble = new ListaDoble<>();
        doble.agregarFinal(1.5);
        doble.agregarInicio(0.5);
        assertEquals("[0.5,1.5]", JsonEscritor.escribir(doble));
    }

    @Test
    void escribeRecordsDelProyecto() {
        Vela vela = new Vela(1000, 10.5, 12, 9, 11, 100.25, 1999);
        assertEquals("{\"tiempoApertura\":1000,\"apertura\":10.5,\"maximo\":12,\"minimo\":9,"
                + "\"cierre\":11,\"volumen\":100.25,\"tiempoCierre\":1999}", JsonEscritor.escribir(vela));
    }

    @Test
    void escribeRecordsPrivadosConCamposCompuestos() {
        Lista<Integer> etiquetas = new Lista<>();
        etiquetas.agregar(7);
        assertEquals("{\"nombre\":\"p\",\"x\":1.25,\"etiquetas\":[7]}",
                JsonEscritor.escribir(new Punto("p", 1.25, etiquetas)));
    }

    @Test
    void escribeEnumsPorNombre() {
        assertEquals("\"D1\"", JsonEscritor.escribir(Intervalo.D1));
    }

    @Test
    void rechazaTiposNoSoportados() {
        assertThrows(IllegalArgumentException.class, () -> JsonEscritor.escribir(new Object()));
    }

    @Test
    void idaYVueltaConElLector() {
        String json = "{\"precio\":67000.5,\"velas\":[[1,\"2\"],[]],\"ok\":false,\"nada\":null,"
                + "\"texto\":\"línea\\n\\\"citada\\\"\"}";
        String reescrito = JsonEscritor.escribir(JsonLector.leer(json));
        assertEquals(json, reescrito);
        assertEquals(reescrito, JsonEscritor.escribir(JsonLector.leer(reescrito)));
    }
}
