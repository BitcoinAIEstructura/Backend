package com.bitcoinai.backend.api;

import static com.bitcoinai.backend.api.ClienteHttpPrueba.get;
import static org.junit.jupiter.api.Assertions.assertEquals;

import com.bitcoinai.backend.mercado.ClienteBinance;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * Simula un despliegue en una región que Binance bloquea (responde 451):
 * /health sigue funcionando y los endpoints de mercado responden 502.
 */
class RegionRestringidaTest {

    private HttpServer binanceFalso;
    private Servidor servidor;
    private final AtomicInteger peticionesABinance = new AtomicInteger();

    @BeforeEach
    void iniciar() throws IOException {
        binanceFalso = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
        binanceFalso.createContext("/", ex -> {
            peticionesABinance.incrementAndGet();
            byte[] cuerpo = "{\"code\":0,\"msg\":\"restricted location\"}".getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(451, cuerpo.length);
            try (OutputStream salida = ex.getResponseBody()) {
                salida.write(cuerpo);
            }
        });
        binanceFalso.start();
        ClienteBinance cliente = new ClienteBinance("http://127.0.0.1:" + binanceFalso.getAddress().getPort(),
                HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build(),
                Duration.ofSeconds(5), 1, Duration.ZERO);
        servidor = new Servidor("127.0.0.1", 0, new RutasApi(cliente, "BTCUSDT").crearRouter(), "*");
        servidor.iniciar();
    }

    @AfterEach
    void detener() {
        servidor.detener(0);
        binanceFalso.stop(0);
    }

    @Test
    void healthNoDependeDeBinance() {
        assertEquals(200, get(servidor.puerto(), "/health").statusCode());
        assertEquals(0, peticionesABinance.get());
    }

    @Test
    void losEndpointsDeMercadoResponden502() {
        assertEquals(502, get(servidor.puerto(), "/api/velas?intervalo=1d&cantidad=5").statusCode());
        assertEquals(502, get(servidor.puerto(), "/api/precio").statusCode());
        assertEquals(200, get(servidor.puerto(), "/health").statusCode());
    }
}
