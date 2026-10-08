package com.bitcoinai.backend.api;

import static com.bitcoinai.backend.api.PublicadorTest.esperarHasta;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.simulacion.Cartera;
import com.bitcoinai.backend.simulacion.LibroDeOrdenes;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.Socket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** /api/stream de punta a punta, con clientes HTTP reales. */
class StreamApiTest {

    private FuenteFalsa fuente;
    private Publicador publicador;
    private LibroDeOrdenes libro;
    private Servidor servidor;
    private int puerto;

    @BeforeEach
    void iniciar() throws IOException {
        fuente = new FuenteFalsa();
        // Máximo 2 conexiones; el precio y el latido se disparan a mano en las pruebas.
        publicador = new Publicador(fuente, "BTCUSDT", 2, Duration.ofHours(1), Duration.ofHours(1));
        libro = new LibroDeOrdenes(new Cartera(), fuente, "BTCUSDT");
        libro.usarPublicador(publicador);
        servidor = new Servidor("127.0.0.1", 0, new RutasApi(fuente, "BTCUSDT").crearRouter(), "https://panel.app");
        servidor.agregarStream(publicador);
        servidor.iniciar();
        puerto = servidor.puerto();
    }

    @AfterEach
    void detener() {
        publicador.detener(); // libera las conexiones abiertas
        servidor.detener(0);
    }

    /** Abre /api/stream con HttpClient y va dejando cada línea recibida en una cola. */
    private BlockingQueue<String> abrirStream(HttpResponse<?>[] respuesta) throws Exception {
        BlockingQueue<String> lineas = new LinkedBlockingQueue<>();
        HttpClient cliente = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build();
        HttpRequest peticion = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + puerto + "/api/stream")).build();
        HttpResponse<Stream<String>> r = cliente.sendAsync(peticion, HttpResponse.BodyHandlers.ofLines())
                .get(5, TimeUnit.SECONDS);
        respuesta[0] = r;
        Thread lector = new Thread(() -> r.body().forEach(lineas::add), "lector-sse");
        lector.setDaemon(true);
        lector.start();
        return lineas;
    }

    /** Espera una línea que empiece con el prefijo y la devuelve. */
    private static String esperarLinea(BlockingQueue<String> lineas, String prefijo) throws InterruptedException {
        long limite = System.currentTimeMillis() + 5_000;
        while (System.currentTimeMillis() < limite) {
            String linea = lineas.poll(100, TimeUnit.MILLISECONDS);
            if (linea != null && linea.startsWith(prefijo)) {
                return linea;
            }
        }
        throw new AssertionError("No llegó una línea que empiece con: " + prefijo);
    }

    /** Conexión cruda por socket, para poder cortarla de golpe como un cliente que se va. */
    private Socket abrirSocketStream() throws IOException {
        Socket socket = new Socket("127.0.0.1", puerto);
        OutputStream salida = socket.getOutputStream();
        salida.write("GET /api/stream HTTP/1.1\r\nHost: localhost\r\n\r\n".getBytes(StandardCharsets.US_ASCII));
        salida.flush();
        BufferedReader entrada = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
        socket.setSoTimeout(5_000);
        String linea;
        while ((linea = entrada.readLine()) != null) {
            if (linea.contains(": conectado")) {
                return socket;
            }
        }
        throw new AssertionError("El stream no saludó");
    }

    @Test
    void unClienteHttpRecibeLosEventos() throws Exception {
        HttpResponse<?>[] respuesta = new HttpResponse<?>[1];
        BlockingQueue<String> lineas = abrirStream(respuesta);
        assertEquals(200, respuesta[0].statusCode());
        assertEquals("text/event-stream; charset=utf-8", respuesta[0].headers().firstValue("Content-Type").orElse(""));
        assertEquals("https://panel.app", respuesta[0].headers().firstValue("Access-Control-Allow-Origin").orElse(""));
        esperarHasta(() -> publicador.cantidadSuscriptores() == 1, "suscripción");

        fuente.setPrecio(84_000);
        publicador.publicarPrecio();
        esperarLinea(lineas, "event: precio");
        assertTrue(esperarLinea(lineas, "data: ").contains("\"precio\":84000"));

        // El libro de órdenes publica por la interfaz y el cliente lo recibe.
        libro.crearCompra(100, null);
        esperarLinea(lineas, "event: orden");
        assertTrue(esperarLinea(lineas, "data: ").contains("\"estado\":\"PENDIENTE\""));
        libro.procesarSiguiente();
        esperarLinea(lineas, "event: cartera");
        assertTrue(esperarLinea(lineas, "data: ").contains("\"saldoUsdt\":9900"));

        publicador.enviarLatido();
        esperarLinea(lineas, ": latido");
    }

    @Test
    void alDesconectarseElClienteSeQuitaDeLaLista() throws Exception {
        Socket socket = abrirSocketStream();
        esperarHasta(() -> publicador.cantidadSuscriptores() == 1, "suscripción");
        socket.close();
        // El servidor se entera al fallar una escritura: el latido lo provoca.
        esperarHasta(() -> {
            publicador.enviarLatido();
            return publicador.cantidadSuscriptores() == 0;
        }, "que se quite al desconectado");
    }

    @Test
    void superarElLimiteDeConexionesDa503() throws Exception {
        try (Socket uno = abrirSocketStream(); Socket dos = abrirSocketStream()) {
            esperarHasta(() -> publicador.cantidadSuscriptores() == 2, "dos suscripciones");
            HttpResponse<String> r = ClienteHttpPrueba.get(puerto, "/api/stream");
            assertEquals(503, r.statusCode());
            assertTrue(r.body().contains("Demasiadas conexiones"), r.body());
            assertEquals("application/json; charset=utf-8", r.headers().firstValue("Content-Type").orElse(""));
        }
        // Al cerrar, se liberan los lugares.
        esperarHasta(() -> {
            publicador.enviarLatido();
            return publicador.cantidadSuscriptores() == 0;
        }, "que se liberen los lugares");
        try (Socket otra = abrirSocketStream()) {
            esperarHasta(() -> publicador.cantidadSuscriptores() == 1, "nueva suscripción");
        }
    }

    @Test
    void metodoYRutaIncorrectos() {
        HttpResponse<String> post = ClienteHttpPrueba.pedir(puerto, "POST", "/api/stream");
        assertEquals(405, post.statusCode());
        assertEquals("GET", post.headers().firstValue("Allow").orElse(""));
        assertEquals(404, ClienteHttpPrueba.get(puerto, "/api/streamx").statusCode());
        assertEquals(200, ClienteHttpPrueba.get(puerto, "/health").statusCode());
    }
}
