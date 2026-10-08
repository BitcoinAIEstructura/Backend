package com.bitcoinai.backend.util;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import java.util.Map;
import org.junit.jupiter.api.Test;

class JsonLectorTest {

    @SuppressWarnings("unchecked")
    private static Map<String, Object> objeto(Object valor) {
        return (Map<String, Object>) assertInstanceOf(Map.class, valor);
    }

    @SuppressWarnings("unchecked")
    private static Lista<Object> arreglo(Object valor) {
        return (Lista<Object>) assertInstanceOf(Lista.class, valor);
    }

    private static void assertErrorEn(int posicion, String json) {
        JsonException e = assertThrows(JsonException.class, () -> JsonLector.leer(json));
        assertEquals(posicion, e.getPosicion(), "mensaje: " + e.getMessage());
        assertTrue(e.getMessage().contains("(posición " + posicion + ")"));
    }

    // ---------- casos válidos ----------

    @Test
    void leeValoresSimples() {
        assertEquals("hola", JsonLector.leer("\"hola\""));
        assertEquals(42.0, JsonLector.leer("42"));
        assertEquals(Boolean.TRUE, JsonLector.leer("true"));
        assertEquals(Boolean.FALSE, JsonLector.leer("false"));
        assertNull(JsonLector.leer("null"));
    }

    @Test
    void leeNumerosNegativosDecimalesYConExponente() {
        assertEquals(-7.0, JsonLector.leer("-7"));
        assertEquals(0.0, JsonLector.leer("0"));
        assertEquals(-0.5, JsonLector.leer("-0.5"));
        assertEquals(3.25, JsonLector.leer("3.25"));
        assertEquals(1500.0, JsonLector.leer("1.5e3"));
        assertEquals(0.012, JsonLector.leer("1.2E-2"));
        assertEquals(200.0, JsonLector.leer("2e+2"));
        assertEquals(1499040000000.0, JsonLector.leer("1499040000000"));
    }

    @Test
    void leeObjetoConVariosTiposYConservaElOrden() {
        Map<String, Object> o = objeto(JsonLector.leer(
                "{\"z\": 1, \"a\": \"x\", \"m\": [true, null], \"b\": {\"c\": -2.5}}"));
        assertEquals("[z, a, m, b]", o.keySet().toString());
        assertEquals(1.0, o.get("z"));
        assertEquals("x", o.get("a"));
        Lista<Object> m = arreglo(o.get("m"));
        assertEquals(Boolean.TRUE, m.obtener(0));
        assertNull(m.obtener(1));
        assertEquals(-2.5, objeto(o.get("b")).get("c"));
    }

    @Test
    void leeArreglosAnidadosComoListaDelProyecto() {
        Lista<Object> externo = arreglo(JsonLector.leer("[[1, 2], [], [[3]]]"));
        assertEquals(3, externo.tamanio());
        assertEquals(2, arreglo(externo.obtener(0)).tamanio());
        assertEquals(0, arreglo(externo.obtener(1)).tamanio());
        assertEquals(3.0, arreglo(arreglo(externo.obtener(2)).obtener(0)).obtener(0));
    }

    @Test
    void objetoYArregloVacios() {
        assertTrue(objeto(JsonLector.leer("{}")).isEmpty());
        assertTrue(objeto(JsonLector.leer("{ \n }")).isEmpty());
        assertTrue(arreglo(JsonLector.leer("[ ]")).estaVacia());
    }

    @Test
    void ignoraEspaciosTabulacionesYSaltosDeLinea() {
        Map<String, Object> o = objeto(JsonLector.leer(" \t\r\n{ \"a\" :\n\t[ 1 ,2 ] }\n "));
        assertEquals(2, arreglo(o.get("a")).tamanio());
    }

    @Test
    void interpretaLosEscapes() {
        // JSON: "\" \\ \/ \b \f \n \r \t \u00e9 \ud83d\ude00"
        String json = "\"\\\" \\\\ \\/ \\b \\f \\n \\r \\t \\u00e9 \\ud83d\\ude00\"";
        assertEquals("\" \\ / \b \f \n \r \t é 😀", JsonLector.leer(json));
    }

    @Test
    void claveRepetidaSeQuedaConElUltimoValor() {
        assertEquals(2.0, objeto(JsonLector.leer("{\"a\":1,\"a\":2}")).get("a"));
    }

    // ---------- casos inválidos, con la posición del error ----------

    @Test
    void textoVacioONulo() {
        assertErrorEn(0, "");
        assertErrorEn(3, "   ");
        assertThrows(JsonException.class, () -> JsonLector.leer(null));
    }

    @Test
    void comasSobrantesOFaltantes() {
        assertErrorEn(7, "{\"a\":1,}");
        assertErrorEn(3, "[1,]");
        assertErrorEn(3, "[1 2]");
        assertErrorEn(7, "{\"a\":1 \"b\":2}");
    }

    @Test
    void objetosMalFormados() {
        assertErrorEn(1, "{1:2}");
        assertErrorEn(5, "{\"a\" 1}");
        assertErrorEn(6, "{\"a\":1");
        assertErrorEn(2, "[1");
    }

    @Test
    void textosMalFormados() {
        assertErrorEn(4, "\"abc");
        assertErrorEn(3, "\"a\\x\"");
        assertErrorEn(2, "\"a" + (char) 1 + "\"");
        assertErrorEn(5, "\"\\u12G4\"");
        assertErrorEn(3, "\"\\u12");
    }

    @Test
    void numerosMalFormados() {
        assertErrorEn(1, "01");
        assertErrorEn(1, "-");
        assertErrorEn(1, "-a");
        assertErrorEn(2, "1.");
        assertErrorEn(2, "1e");
        assertErrorEn(0, "+1");
        assertErrorEn(0, ".5");
    }

    @Test
    void literalesInvalidosYContenidoExtra() {
        assertErrorEn(0, "tru");
        assertErrorEn(0, "nul");
        assertErrorEn(0, "True");
        assertErrorEn(2, "1 2");
        assertErrorEn(2, "{}x");
    }

    @Test
    void anidamientoExcesivoSeRechazaSinDesbordarLaPila() {
        String profundo = "[".repeat(10_000) + "]".repeat(10_000);
        assertThrows(JsonException.class, () -> JsonLector.leer(profundo));
        String aceptable = "[".repeat(100) + "]".repeat(100);
        assertInstanceOf(Lista.class, JsonLector.leer(aceptable));
    }
}
