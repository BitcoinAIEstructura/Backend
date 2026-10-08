package com.bitcoinai.backend.api;

import static com.bitcoinai.backend.api.ClienteHttpPrueba.get;
import static com.bitcoinai.backend.api.ClienteHttpPrueba.json;
import static com.bitcoinai.backend.api.ClienteHttpPrueba.pedir;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estrategia.EstrategiaCombinada;
import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.mercado.MercadoException;
import com.bitcoinai.backend.simulacion.BotSimulado;
import com.bitcoinai.backend.simulacion.Cartera;
import com.bitcoinai.backend.simulacion.LibroDeOrdenes;
import java.io.IOException;
import java.net.http.HttpResponse;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** Pruebas de los endpoints de órdenes, cartera, historial y bot, con una FuenteFalsa a precio 100. */
class SimulacionApiTest {

    private FuenteFalsa fuente;
    private BotSimulado bot;
    private Servidor servidor;
    private int puerto;

    @BeforeEach
    void iniciar() throws IOException {
        fuente = new FuenteFalsa();
        LibroDeOrdenes libro = new LibroDeOrdenes(new Cartera(), fuente, "BTCUSDT");
        bot = new BotSimulado(libro, fuente, new EstrategiaCombinada(), "BTCUSDT");
        Router router = new RutasApi(fuente, "BTCUSDT").crearRouter();
        new RutasSimulacion(libro, bot).registrar(router);
        servidor = new Servidor("127.0.0.1", 0, router, "*");
        servidor.iniciar();
        puerto = servidor.puerto();
    }

    @AfterEach
    void detener() {
        bot.detener();
        servidor.detener(0);
    }

    private HttpResponse<String> post(String ruta, String cuerpo) {
        return ClienteHttpPrueba.enviar(puerto, "POST", ruta, cuerpo);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> mapa(Object valor) {
        return (Map<String, Object>) valor;
    }

    private void assertError(HttpResponse<String> r, int codigo, String fragmento) {
        assertEquals(codigo, r.statusCode(), r.body());
        String mensaje = (String) json(r).get("error");
        assertTrue(mensaje.contains(fragmento), "mensaje: " + mensaje);
    }

    // ---------- flujo completo ----------

    @Test
    void crearProcesarYVerElCambioEnLaCartera() {
        HttpResponse<String> creada = post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":500}");
        assertEquals(201, creada.statusCode(), creada.body());
        Map<String, Object> orden = json(creada);
        assertEquals(1.0, orden.get("id"));
        assertEquals("PENDIENTE", orden.get("estado"));
        assertEquals("manual", orden.get("motivo"));

        HttpResponse<String> procesada = post("/api/ordenes/procesar", "");
        assertEquals(200, procesada.statusCode());
        assertEquals("EJECUTADA", json(procesada).get("estado"));
        assertEquals(100.0, json(procesada).get("precioEjecucion"));

        Map<String, Object> cartera = json(get(puerto, "/api/cartera"));
        assertEquals(9_500.0, cartera.get("saldoUsdt"));
        assertEquals(4.995, (Double) cartera.get("btc"), 1e-12);
        assertEquals(100.0, cartera.get("precioActual"));
        assertEquals(10_000.0, cartera.get("saldoInicial"));
    }

    @Test
    void ventaDeTodoPorApi() {
        post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":1000}");
        post("/api/ordenes/procesar", "");
        assertEquals(201, post("/api/ordenes", "{\"tipo\":\"VENTA\",\"todo\":true,\"motivo\":\"salir\"}").statusCode());
        Map<String, Object> venta = json(post("/api/ordenes/procesar", ""));
        assertEquals("salir", venta.get("motivo"));
        assertEquals(0.0, json(get(puerto, "/api/cartera")).get("btc"));
    }

    @Test
    void listarFiltrarObtenerYCancelar() {
        post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":100}");
        post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":200}");
        post("/api/ordenes", "{\"tipo\":\"compra\",\"monto\":300}");

        HttpResponse<String> cancelada = pedir(puerto, "DELETE", "/api/ordenes/2");
        assertEquals(200, cancelada.statusCode());
        assertEquals("CANCELADA", json(cancelada).get("estado"));

        Map<String, Object> pendientes = json(get(puerto, "/api/ordenes?estado=pendiente"));
        assertEquals(2.0, pendientes.get("cantidad"));
        Lista<?> lista = (Lista<?>) pendientes.get("ordenes");
        assertEquals(1.0, mapa(lista.obtener(0)).get("id"));
        assertEquals(3.0, mapa(lista.obtener(1)).get("id"));

        assertEquals(3.0, json(get(puerto, "/api/ordenes")).get("cantidad"));
        assertEquals("CANCELADA", json(get(puerto, "/api/ordenes/2")).get("estado"));
    }

    @Test
    void deshacerLaUltimaOrden() {
        post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":100}");
        post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":200}");
        HttpResponse<String> r = post("/api/ordenes/deshacer", "");
        assertEquals(200, r.statusCode());
        assertEquals(2.0, json(r).get("id"));
        assertEquals(1.0, json(get(puerto, "/api/ordenes?estado=PENDIENTE")).get("cantidad"));
    }

    @Test
    void historialConLimite() {
        post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":100}");
        post("/api/ordenes/procesar", "");
        Lista<?> eventos = (Lista<?>) json(get(puerto, "/api/historial?limite=1")).get("eventos");
        assertEquals(1, eventos.tamanio());
        assertEquals("ORDEN_EJECUTADA", mapa(eventos.primero()).get("tipo"));
        assertEquals(2, ((Lista<?>) json(get(puerto, "/api/historial")).get("eventos")).tamanio());
    }

    // ---------- validación del cuerpo ----------

    @Test
    void cuerposInvalidosDan400ConElMotivo() {
        assertError(post("/api/ordenes", ""), 400, "Falta el cuerpo JSON");
        assertError(post("/api/ordenes", "no es json"), 400, "Cuerpo JSON inválido");
        assertError(post("/api/ordenes", "[1,2]"), 400, "objeto JSON");
        assertError(post("/api/ordenes", "{\"monto\":500}"), 400, "Falta el campo 'tipo'");
        assertError(post("/api/ordenes", "{\"tipo\":\"PRESTAMO\",\"monto\":500}"), 400, "COMPRA, VENTA");
        assertError(post("/api/ordenes", "{\"tipo\":\"COMPRA\"}"), 400, "Falta el campo 'monto'");
        assertError(post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":0}"), 400, "mayor que 0");
        assertError(post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":-5}"), 400, "mayor que 0");
        assertError(post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":\"500\"}"), 400, "debe ser un número");
        assertError(post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"todo\":true}"), 400, "solo se usa en órdenes de VENTA");
        assertError(post("/api/ordenes", "{\"tipo\":\"VENTA\",\"todo\":true,\"monto\":5}"), 400, "no se indica 'monto'");
        assertError(post("/api/ordenes", "{\"tipo\":\"VENTA\",\"todo\":\"si\"}"), 400, "'todo'");
        assertEquals(0.0, json(get(puerto, "/api/ordenes")).get("cantidad"));
    }

    @Test
    void erroresDeEstadoYDeId() {
        assertError(post("/api/ordenes/procesar", ""), 409, "No hay órdenes pendientes");
        assertError(post("/api/ordenes/deshacer", ""), 409, "No hay una orden");
        assertError(pedir(puerto, "DELETE", "/api/ordenes/99"), 404, "No existe la orden #99");
        assertError(get(puerto, "/api/ordenes/99"), 404, "#99");
        assertError(pedir(puerto, "DELETE", "/api/ordenes/abc"), 400, "Id de orden inválido");
        post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":100}");
        post("/api/ordenes/procesar", "");
        assertError(pedir(puerto, "DELETE", "/api/ordenes/1"), 409, "ya no está pendiente");
        assertError(get(puerto, "/api/ordenes?estado=RARA"), 400, "'estado'");
        assertError(get(puerto, "/api/historial?limite=0"), 400, "'limite'");
    }

    @Test
    void siFallaElPrecioResponde502YLaOrdenSigueEnLaCola() {
        post("/api/ordenes", "{\"tipo\":\"COMPRA\",\"monto\":100}");
        fuente.setError(new MercadoException("caída"));
        assertEquals(502, post("/api/ordenes/procesar", "").statusCode());
        assertEquals(502, get(puerto, "/api/cartera").statusCode());
        fuente.setError(null);
        assertEquals("PENDIENTE", json(get(puerto, "/api/ordenes/1")).get("estado"));
    }

    // ---------- bot ----------

    @Test
    void iniciarConsultarYDetenerElBot() {
        assertEquals(false, json(get(puerto, "/api/bot/estado")).get("activo"));

        HttpResponse<String> iniciado = post("/api/bot/iniciar", "{\"segundosEntreCiclos\":3600,\"riesgo\":0.1,\"intervalo\":\"1d\"}");
        assertEquals(200, iniciado.statusCode(), iniciado.body());
        Map<String, Object> estado = json(iniciado);
        assertEquals(true, estado.get("activo"));
        assertEquals("combinada", estado.get("estrategia"));
        Map<String, Object> configuracion = mapa(estado.get("configuracion"));
        assertEquals(3600.0, configuracion.get("segundosEntreCiclos"));
        assertEquals(0.1, configuracion.get("riesgo"));
        assertEquals("1d", configuracion.get("intervalo"));
        assertEquals(0.05, configuracion.get("stopLoss")); // por defecto

        assertError(post("/api/bot/iniciar", ""), 409, "ya está en marcha");
        assertEquals(false, json(post("/api/bot/detener", "")).get("activo"));
        assertEquals(false, json(post("/api/bot/detener", "")).get("activo"));
    }

    @Test
    void configuracionDelBotInvalidaDa400() {
        assertError(post("/api/bot/iniciar", "{\"riesgo\":2}"), 400, "'riesgo'");
        assertError(post("/api/bot/iniciar", "{\"intervalo\":\"2h\"}"), 400, "Intervalo no soportado");
        assertError(post("/api/bot/iniciar", "{\"segundosEntreCiclos\":1.5}"), 400, "entero");
        assertError(post("/api/bot/iniciar", "{\"stopLoss\":\"x\"}"), 400, "'stopLoss'");
        assertEquals(false, json(get(puerto, "/api/bot/estado")).get("activo"));
    }
}
