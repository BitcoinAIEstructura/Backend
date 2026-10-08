package com.bitcoinai.backend.mercado;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

/**
 * Pruebas del cliente contra un servidor HTTP local que imita a Binance.
 * No usan internet.
 */
class ClienteBinanceTest {

    private static final long DIA = Intervalo.D1.milisegundos();
    private static final long INICIO = 1_600_000_000_000L;

    private HttpServer servidor;
    private final AtomicInteger peticiones = new AtomicInteger();
    private volatile String ultimaConsulta;
    private volatile String ultimaRuta;

    @AfterEach
    void detenerServidor() {
        if (servidor != null) {
            servidor.stop(0);
        }
    }

    // ---------- conversión de klines ----------

    @Test
    void convierteUnaRespuestaDeKlinesEscritaAMano() {
        String json = """
                [
                  [1499040000000, "0.01634790", "0.80000000", "0.01575800", "0.01577100",
                   "148976.11427815", 1499644799999, "2434.19055334", 308, "1756.87402397",
                   "28.46694368", "0"],
                  [1499644800000, "0.01577100", "0.02000000", "0.01500000", "0.01900000",
                   "1000.5", 1500249599999, "20.0", 10, "500.0", "9.0", "0"]
                ]
                """;
        ListaDoble<Vela> velas = ClienteBinance.convertirKlines(json);
        assertEquals(2, velas.tamanio());
        assertEquals(new Vela(1499040000000L, 0.01634790, 0.80000000, 0.01575800, 0.01577100,
                148976.11427815, 1499644799999L), velas.primero());
        assertEquals(1499644800000L, velas.ultimo().tiempoApertura());
        assertEquals(0.019, velas.ultimo().cierre());
        assertEquals(1500249599999L, velas.ultimo().tiempoCierre());
    }

    @Test
    void convertirKlinesRechazaFormatosInvalidos() {
        assertThrows(MercadoException.class, () -> ClienteBinance.convertirKlines("{}"));
        assertThrows(MercadoException.class, () -> ClienteBinance.convertirKlines("[[1, \"2\", \"3\"]]"));
        assertThrows(MercadoException.class,
                () -> ClienteBinance.convertirKlines("[[1, \"abc\", \"3\", \"1\", \"2\", \"5\", 9]]"));
        assertThrows(MercadoException.class, () -> ClienteBinance.convertirKlines("no es json"));
        assertEquals(0, ClienteBinance.convertirKlines("[]").tamanio());
    }

    // ---------- velas ----------

    @Test
    void pocasVelasSePidenEnUnaSolaPeticion() throws IOException {
        ClienteBinance cliente = clienteCon(historial(50, false));
        ListaDoble<Vela> velas = cliente.obtenerVelas("btcusdt", Intervalo.D1, 10);

        assertEquals(10, velas.tamanio());
        assertEquals(1, peticiones.get());
        assertEquals("/api/v3/klines", ultimaRuta);
        assertEquals("symbol=BTCUSDT&interval=1d&limit=10", ultimaConsulta);
        assertEquals(INICIO + 40 * DIA, velas.primero().tiempoApertura());
        assertEquals(INICIO + 49 * DIA, velas.ultimo().tiempoApertura());
    }

    @Test
    void masDeMilVelasSePaginanHaciaAtrasSinDuplicados() throws IOException {
        ClienteBinance cliente = clienteCon(historial(2500, false));
        ListaDoble<Vela> velas = cliente.obtenerVelas("BTCUSDT", Intervalo.D1, 2300);

        assertEquals(2300, velas.tamanio());
        assertEquals(3, peticiones.get()); // 1000 + 1000 + 300
        assertEquals(INICIO + 200 * DIA, velas.primero().tiempoApertura());
        assertEquals(INICIO + 2499 * DIA, velas.ultimo().tiempoApertura());
        assertConsecutivas(velas);
    }

    @Test
    void siLaFuenteDevuelveVelasSolapadasSeDescartanLosDuplicados() throws IOException {
        ClienteBinance cliente = clienteCon(historial(3000, true));
        ListaDoble<Vela> velas = cliente.obtenerVelas("BTCUSDT", Intervalo.D1, 2500);

        assertEquals(2500, velas.tamanio());
        assertEquals(INICIO + 2999 * DIA, velas.ultimo().tiempoApertura());
        assertConsecutivas(velas);
    }

    @Test
    void siNoHayTantoHistorialDevuelveLoQueExiste() throws IOException {
        ClienteBinance cliente = clienteCon(historial(1500, false));
        ListaDoble<Vela> velas = cliente.obtenerVelas("BTCUSDT", Intervalo.D1, 3000);

        assertEquals(1500, velas.tamanio());
        assertEquals(2, peticiones.get());
        assertEquals(INICIO, velas.primero().tiempoApertura());
        assertConsecutivas(velas);
    }

    @Test
    void velasIncoherentesDeLaFuenteLanzanMercadoException() throws IOException {
        // máximo (5) menor que mínimo (9)
        ClienteBinance cliente = clienteCon(ex -> responder(ex, 200,
                "[[1000, \"6\", \"5\", \"9\", \"7\", \"1\", 1999]]"));
        assertThrows(MercadoException.class, () -> cliente.obtenerVelas("BTCUSDT", Intervalo.D1, 1));
    }

    @Test
    void parametrosInvalidosNoHacenPeticiones() throws IOException {
        ClienteBinance cliente = clienteCon(historial(10, false));
        assertThrows(IllegalArgumentException.class, () -> cliente.obtenerVelas("BTCUSDT", Intervalo.D1, 0));
        assertThrows(IllegalArgumentException.class, () -> cliente.obtenerVelas("BTC/USDT&x=1", Intervalo.D1, 5));
        assertThrows(IllegalArgumentException.class, () -> cliente.obtenerPrecioActual(" "));
        assertEquals(0, peticiones.get());
    }

    // ---------- precio ----------

    @Test
    void obtienePrecioActual() throws IOException {
        ClienteBinance cliente = clienteCon(ex -> responder(ex, 200,
                "{\"symbol\":\"BTCUSDT\",\"price\":\"67123.45000000\"}"));
        assertEquals(67123.45, cliente.obtenerPrecioActual("BTCUSDT"));
        assertEquals("/api/v3/ticker/price", ultimaRuta);
        assertEquals("symbol=BTCUSDT", ultimaConsulta);
    }

    @Test
    void precioSinCampoPriceOInvalidoLanza() throws IOException {
        ClienteBinance cliente = clienteCon(ex -> responder(ex, 200, "{\"symbol\":\"BTCUSDT\"}"));
        assertThrows(MercadoException.class, () -> cliente.obtenerPrecioActual("BTCUSDT"));
    }

    // ---------- errores y reintentos ----------

    @Test
    void error4xxIncluyeElMensajeDeBinanceYNoSeReintenta() throws IOException {
        ClienteBinance cliente = clienteCon(ex -> responder(ex, 400,
                "{\"code\":-1121,\"msg\":\"Invalid symbol.\"}"));
        MercadoException e = assertThrows(MercadoException.class,
                () -> cliente.obtenerVelas("NOEXISTE", Intervalo.D1, 5));
        assertEquals("Binance respondió HTTP 400: Invalid symbol.", e.getMessage());
        assertEquals(1, peticiones.get());
    }

    @Test
    void error451DeRegionRestringidaDaUnMensajeClaroYNoSeReintenta() throws IOException {
        ClienteBinance cliente = clienteCon(ex -> responder(ex, 451,
                "{\"code\":0,\"msg\":\"Service unavailable from a restricted location\"}"));
        MercadoException e = assertThrows(MercadoException.class,
                () -> cliente.obtenerVelas("BTCUSDT", Intervalo.D1, 5));
        assertEquals("Binance no está disponible desde esta región; cambia la región del servicio o la URL base",
                e.getMessage());
        assertEquals(ClienteBinance.MENSAJE_REGION_RESTRINGIDA, e.getMessage());
        assertEquals(1, peticiones.get());
        assertThrows(MercadoException.class, () -> cliente.obtenerPrecioActual("BTCUSDT"));
    }

    @Test
    void error5xxSeReintentaUnaVezYSiFuncionaDevuelveElDato() throws IOException {
        ClienteBinance cliente = clienteCon(ex -> {
            if (peticiones.get() == 1) {
                responder(ex, 503, "Servicio no disponible");
            } else {
                responder(ex, 200, "{\"price\":\"100.5\"}");
            }
        });
        assertEquals(100.5, cliente.obtenerPrecioActual("BTCUSDT"));
        assertEquals(2, peticiones.get());
    }

    @Test
    void error5xxPersistenteLanzaDespuesDelReintento() throws IOException {
        ClienteBinance cliente = clienteCon(ex -> responder(ex, 500, "error interno"));
        MercadoException e = assertThrows(MercadoException.class, () -> cliente.obtenerPrecioActual("BTCUSDT"));
        assertEquals("Binance respondió HTTP 500", e.getMessage());
        assertEquals(2, peticiones.get());
    }

    @Test
    void respuestaLentaAgotaElTiempoDeEspera() throws IOException {
        servidor = crearServidor(ex -> {
            peticiones.incrementAndGet();
            try {
                Thread.sleep(1_000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            responder(ex, 200, "{\"price\":\"1\"}");
        });
        ClienteBinance cliente = new ClienteBinance(url(), httpClient(), Duration.ofMillis(150), 1, Duration.ZERO);
        MercadoException e = assertThrows(MercadoException.class, () -> cliente.obtenerPrecioActual("BTCUSDT"));
        assertEquals("Binance no respondió a tiempo", e.getMessage());
        assertEquals(2, peticiones.get());
    }

    @Test
    void sinServidorLanzaErrorDeConexion() throws IOException {
        int puertoLibre;
        try (ServerSocket socket = new ServerSocket(0, 1, InetAddress.getLoopbackAddress())) {
            puertoLibre = socket.getLocalPort();
        }
        ClienteBinance cliente = new ClienteBinance("http://127.0.0.1:" + puertoLibre,
                httpClient(), Duration.ofSeconds(2), 1, Duration.ZERO);
        MercadoException e = assertThrows(MercadoException.class, () -> cliente.obtenerPrecioActual("BTCUSDT"));
        assertTrue(e.getMessage().startsWith("No se pudo conectar con Binance"), e.getMessage());
    }

    // ---------- configuración ----------

    @Test
    void resolverUrlBaseUsaElValorPorDefectoYQuitaLaBarraFinal() {
        assertEquals("https://api.binance.com", ClienteBinance.resolverUrlBase(null));
        assertEquals("https://api.binance.com", ClienteBinance.resolverUrlBase("  "));
        assertEquals("https://api.binance.us", ClienteBinance.resolverUrlBase(" https://api.binance.us/ "));
        assertEquals("https://data-api.binance.vision",
                new ClienteBinance("https://data-api.binance.vision/").getUrlBase());
    }

    // ---------- utilidades del servidor falso ----------

    /**
     * Imita /api/v3/klines con un historial de {@code total} velas diarias: devuelve
     * las últimas {@code limit} con tiempo de apertura &lt;= endTime. Si
     * {@code solapar} es true, incluye además una vela posterior a endTime, para
     * comprobar que el cliente descarta duplicados.
     */
    private HttpHandler historial(int total, boolean solapar) {
        return ex -> {
            String consulta = ex.getRequestURI().getQuery();
            int limite = Integer.parseInt(parametro(consulta, "limit"));
            String fin = parametro(consulta, "endTime");
            int ultimo = total - 1;
            if (fin != null) {
                ultimo = (int) Math.min(total - 1, Math.floorDiv(Long.parseLong(fin) - INICIO, DIA));
                if (solapar) {
                    ultimo = Math.min(total - 1, ultimo + 1);
                }
            }
            int primero = Math.max(0, ultimo - limite + 1);
            StringBuilder sb = new StringBuilder("[");
            for (int i = primero; i <= ultimo; i++) {
                if (i > primero) {
                    sb.append(',');
                }
                long t = INICIO + i * DIA;
                double p = 100 + i;
                sb.append('[').append(t)
                        .append(",\"").append(p).append("\",\"").append(p + 5)
                        .append("\",\"").append(p - 5).append("\",\"").append(p + 1)
                        .append("\",\"10.0\",").append(t + DIA - 1)
                        .append(",\"0\",1,\"0\",\"0\",\"0\"]");
            }
            responder(ex, 200, sb.append(']').toString());
        };
    }

    private static String parametro(String consulta, String nombre) {
        for (String par : consulta.split("&")) {
            String[] partes = par.split("=", 2);
            if (partes[0].equals(nombre)) {
                return partes[1];
            }
        }
        return null;
    }

    private static void assertConsecutivas(ListaDoble<Vela> velas) {
        Vela anterior = null;
        for (Vela v : velas) {
            if (anterior != null) {
                assertEquals(anterior.tiempoApertura() + DIA, v.tiempoApertura());
            }
            anterior = v;
        }
    }

    private ClienteBinance clienteCon(HttpHandler manejador) throws IOException {
        servidor = crearServidor(ex -> {
            peticiones.incrementAndGet();
            ultimaRuta = ex.getRequestURI().getPath();
            ultimaConsulta = ex.getRequestURI().getQuery();
            manejador.handle(ex);
        });
        return new ClienteBinance(url(), httpClient(), Duration.ofSeconds(5), 1, Duration.ZERO);
    }

    private static HttpServer crearServidor(HttpHandler manejador) throws IOException {
        HttpServer nuevo = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        nuevo.createContext("/", manejador);
        nuevo.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
        nuevo.start();
        return nuevo;
    }

    private String url() {
        return "http://127.0.0.1:" + servidor.getAddress().getPort();
    }

    private static HttpClient httpClient() {
        return HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(2))
                .build();
    }

    private static void responder(HttpExchange ex, int codigo, String cuerpo) throws IOException {
        byte[] bytes = cuerpo.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(codigo, bytes.length);
        try (OutputStream salida = ex.getResponseBody()) {
            salida.write(bytes);
        }
    }
}
