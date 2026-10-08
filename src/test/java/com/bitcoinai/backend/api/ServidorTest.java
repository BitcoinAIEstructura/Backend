package com.bitcoinai.backend.api;

import static com.bitcoinai.backend.api.ClienteHttpPrueba.get;
import static com.bitcoinai.backend.api.ClienteHttpPrueba.json;
import static com.bitcoinai.backend.api.ClienteHttpPrueba.pedir;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.mercado.MercadoException;
import java.io.IOException;
import java.net.http.HttpResponse;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** Pruebas de punta a punta: servidor real en un puerto libre, con una FuenteFalsa. */
class ServidorTest {

    private static final String ORIGEN = "https://panel.ejemplo.com";

    private FuenteFalsa fuente;
    private Servidor servidor;
    private int puerto;

    @BeforeEach
    void iniciar() throws IOException {
        fuente = new FuenteFalsa();
        servidor = new Servidor("127.0.0.1", 0, new RutasApi(fuente, "BTCUSDT").crearRouter(), ORIGEN);
        servidor.iniciar();
        puerto = servidor.puerto();
    }

    @AfterEach
    void detener() {
        servidor.detener(0);
    }

    private static void assertEsJson(HttpResponse<String> respuesta) {
        assertEquals("application/json; charset=utf-8",
                respuesta.headers().firstValue("Content-Type").orElse(""));
    }

    private static void assertError(HttpResponse<String> respuesta, int codigo, String fragmento) {
        assertEquals(codigo, respuesta.statusCode());
        assertEsJson(respuesta);
        Map<String, Object> cuerpo = json(respuesta);
        assertEquals(1, cuerpo.size(), "solo debe venir el campo error");
        String mensaje = (String) cuerpo.get("error");
        assertTrue(mensaje.contains(fragmento), "mensaje: " + mensaje);
    }

    // ---------- respuestas correctas ----------

    @Test
    void healthRespondeOkSinConsultarLaFuente() {
        HttpResponse<String> r = get(puerto, "/health");
        assertEquals(200, r.statusCode());
        assertEsJson(r);
        assertEquals("{\"estado\":\"ok\"}", r.body());
        assertEquals(0, fuente.getLlamadasVelas() + fuente.getLlamadasPrecio());
    }

    @Test
    void healthConBarraFinalTambienFunciona() {
        assertEquals(200, get(puerto, "/health/").statusCode());
    }

    @Test
    void precioDevuelveSimboloPrecioYMomento() {
        fuente.setPrecio(67123.45);
        long antes = System.currentTimeMillis();
        HttpResponse<String> r = get(puerto, "/api/precio");
        assertEquals(200, r.statusCode());
        assertEsJson(r);
        Map<String, Object> cuerpo = json(r);
        assertEquals("BTCUSDT", cuerpo.get("simbolo"));
        assertEquals(67123.45, cuerpo.get("precio"));
        assertTrue((Double) cuerpo.get("momento") >= antes);
    }

    @Test
    void velasConParametros() {
        HttpResponse<String> r = get(puerto, "/api/velas?intervalo=1d&cantidad=5");
        assertEquals(200, r.statusCode());
        assertEsJson(r);
        Map<String, Object> cuerpo = json(r);
        assertEquals("BTCUSDT", cuerpo.get("simbolo"));
        assertEquals("1d", cuerpo.get("intervalo"));
        assertEquals(5.0, cuerpo.get("cantidad"));
        Lista<?> velas = (Lista<?>) cuerpo.get("velas");
        assertEquals(5, velas.tamanio());
        @SuppressWarnings("unchecked")
        Map<String, Object> ultima = (Map<String, Object>) velas.ultimo();
        assertEquals(599.0, ultima.get("apertura")); // FuenteFalsa: vela 499 abre en 100 + 499
        assertEquals("[tiempoApertura, apertura, maximo, minimo, cierre, volumen, tiempoCierre]",
                ultima.keySet().toString());
    }

    @Test
    void velasSinParametrosUsaLosValoresPorDefecto() {
        Map<String, Object> cuerpo = json(get(puerto, "/api/velas"));
        assertEquals("1d", cuerpo.get("intervalo"));
        assertEquals(200.0, cuerpo.get("cantidad"));
    }

    @Test
    void velasAceptaLosLimitesDeCantidad() {
        assertEquals(1, ((Lista<?>) json(get(puerto, "/api/velas?cantidad=1")).get("velas")).tamanio());
        assertEquals(200, get(puerto, "/api/velas?cantidad=1000&intervalo=4h").statusCode());
    }

    // ---------- parámetros inválidos ----------

    @Test
    void intervaloInvalidoDa400ConElMotivo() {
        assertError(get(puerto, "/api/velas?intervalo=2h"), 400, "intervalo");
        assertError(get(puerto, "/api/velas?intervalo=1D"), 400, "1m, 5m, 15m, 1h, 4h, 1d");
    }

    @Test
    void cantidadInvalidaDa400ConElMotivo() {
        assertError(get(puerto, "/api/velas?cantidad=0"), 400, "entre 1 y 1000");
        assertError(get(puerto, "/api/velas?cantidad=1001"), 400, "entre 1 y 1000");
        assertError(get(puerto, "/api/velas?cantidad=abc"), 400, "cantidad");
        assertError(get(puerto, "/api/velas?cantidad=2.5"), 400, "cantidad");
        assertEquals(0, fuente.getLlamadasVelas());
    }

    // ---------- rutas y métodos ----------

    @Test
    void rutaInexistenteDa404EnJson() {
        assertError(get(puerto, "/api/no-existe"), 404, "/api/no-existe");
        assertError(get(puerto, "/"), 404, "Ruta no encontrada");
    }

    @Test
    void metodoNoPermitidoDa405ConEncabezadoAllow() {
        HttpResponse<String> r = pedir(puerto, "POST", "/health");
        assertError(r, 405, "POST");
        assertEquals("GET", r.headers().firstValue("Allow").orElse(""));
        assertError(pedir(puerto, "DELETE", "/api/velas"), 405, "no permitido");
    }

    // ---------- CORS ----------

    @Test
    void lasRespuestasLlevanEncabezadosCors() {
        HttpResponse<String> r = get(puerto, "/health");
        assertEquals(ORIGEN, r.headers().firstValue("Access-Control-Allow-Origin").orElse(""));
        assertEquals("Origin", r.headers().firstValue("Vary").orElse(""));
        HttpResponse<String> error = get(puerto, "/nada");
        assertEquals(ORIGEN, error.headers().firstValue("Access-Control-Allow-Origin").orElse(""));
    }

    @Test
    void optionsRespondePreflightSinLlegarAlManejador() {
        HttpResponse<String> r = pedir(puerto, "OPTIONS", "/api/velas");
        assertEquals(204, r.statusCode());
        assertEquals(ORIGEN, r.headers().firstValue("Access-Control-Allow-Origin").orElse(""));
        assertTrue(r.headers().firstValue("Access-Control-Allow-Methods").orElse("").contains("GET"));
        assertTrue(r.headers().firstValue("Access-Control-Allow-Headers").orElse("").contains("Content-Type"));
        assertEquals("", r.body());
        assertEquals(0, fuente.getLlamadasVelas());
    }

    @Test
    void origenComodinPorDefecto() throws IOException {
        Servidor abierto = new Servidor("127.0.0.1", 0, new RutasApi(fuente, "BTCUSDT").crearRouter(), "*");
        abierto.iniciar();
        try {
            HttpResponse<String> r = get(abierto.puerto(), "/health");
            assertEquals("*", r.headers().firstValue("Access-Control-Allow-Origin").orElse(""));
            assertFalse(r.headers().firstValue("Vary").isPresent());
        } finally {
            abierto.detener(0);
        }
    }

    // ---------- fallos ----------

    @Test
    void siLaFuenteFallaResponde502SinDetallesInternos() {
        fuente.setError(new MercadoException("Binance respondió HTTP 451: detalle interno"));
        HttpResponse<String> velas = get(puerto, "/api/velas?cantidad=5");
        assertError(velas, 502, "Fuente de mercado no disponible");
        assertEquals("{\"error\":\"Fuente de mercado no disponible\"}", velas.body());
        assertError(get(puerto, "/api/precio"), 502, "Fuente de mercado no disponible");
        assertEquals(200, get(puerto, "/health").statusCode());
    }

    @Test
    void errorInesperadoResponde500SinTraza() {
        fuente.setError(new IllegalStateException("secreto interno"));
        HttpResponse<String> r = get(puerto, "/api/precio");
        assertError(r, 500, "Error interno del servidor");
        assertFalse(r.body().contains("secreto"));
        assertFalse(r.body().contains("Exception"));
    }

    @Test
    void detenerDosVecesNoFalla() {
        servidor.detener(0);
        servidor.detener(0);
    }
}
