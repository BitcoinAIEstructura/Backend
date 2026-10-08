package com.bitcoinai.backend.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.mercado.MercadoException;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.function.BooleanSupplier;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

/** Pruebas del Publicador sin HTTP: los suscriptores escriben en memoria. */
class PublicadorTest {

    private final FuenteFalsa fuente = new FuenteFalsa();
    private final Publicador publicador = new Publicador(fuente, "BTCUSDT", 3, Duration.ofHours(1), Duration.ofHours(1));

    @AfterEach
    void detener() {
        publicador.detener();
    }

    static void esperarHasta(BooleanSupplier condicion, String mensaje) {
        long limite = System.currentTimeMillis() + 5_000;
        while (!condicion.getAsBoolean()) {
            if (System.currentTimeMillis() > limite) {
                throw new AssertionError("Se agotó el tiempo esperando: " + mensaje);
            }
            try {
                Thread.sleep(10);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new AssertionError(e);
            }
        }
    }

    private static String texto(ByteArrayOutputStream salida) {
        return salida.toString(StandardCharsets.UTF_8);
    }

    /** Salida que falla al escribir, como un cliente que cerró la conexión. */
    private static final class SalidaRota extends OutputStream {
        volatile boolean rota;

        @Override
        public void write(int b) throws IOException {
            if (rota) {
                throw new IOException("conexión cerrada por el cliente");
            }
        }
    }

    @Test
    void publicaEventosConNombreYJsonEnLaLineaData() throws IOException {
        ByteArrayOutputStream salida = new ByteArrayOutputStream();
        publicador.suscribir(salida).activar();
        publicador.publicar("orden", Map.of("id", 7));
        esperarHasta(() -> texto(salida).contains("event: orden"), "evento orden");
        assertEquals("retry: 5000\n: conectado\n\nevent: orden\ndata: {\"id\":7}\n\n", texto(salida));
    }

    @Test
    void losEventosLleganEnOrdenATodos() throws IOException {
        ByteArrayOutputStream a = new ByteArrayOutputStream();
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        publicador.suscribir(a).activar();
        publicador.suscribir(b).activar();
        for (int i = 1; i <= 20; i++) {
            publicador.publicar("orden", Map.of("id", i));
        }
        esperarHasta(() -> texto(a).contains("{\"id\":20}") && texto(b).contains("{\"id\":20}"), "20 eventos");
        assertTrue(texto(a).indexOf("{\"id\":9}") < texto(a).indexOf("{\"id\":10}"));
        assertEquals(texto(a), texto(b));
    }

    @Test
    void antesDeActivarNoSeEscribeNada() {
        ByteArrayOutputStream salida = new ByteArrayOutputStream();
        publicador.suscribir(salida);
        publicador.publicar("orden", Map.of("id", 1));
        publicador.enviarLatido();
        ByteArrayOutputStream testigo = new ByteArrayOutputStream();
        publicador.suscribir(testigo);
        // un tercero activo confirma que los envíos ya se procesaron
        ByteArrayOutputStream activo = new ByteArrayOutputStream();
        try {
            publicador.desuscribir(publicador.suscribir(activo));
        } catch (ApiException e) {
            // no importa
        }
        assertEquals("", texto(salida));
    }

    @Test
    void latidoEsUnComentario() throws IOException {
        ByteArrayOutputStream salida = new ByteArrayOutputStream();
        publicador.suscribir(salida).activar();
        publicador.enviarLatido();
        esperarHasta(() -> texto(salida).endsWith(": latido\n\n"), "latido");
    }

    @Test
    void precioSoloSePublicaSiHayAlguienEscuchando() throws IOException {
        publicador.publicarPrecio();
        assertEquals(0, fuente.getLlamadasPrecio());

        ByteArrayOutputStream salida = new ByteArrayOutputStream();
        publicador.suscribir(salida).activar();
        fuente.setPrecio(83_000.5);
        publicador.publicarPrecio();
        esperarHasta(() -> texto(salida).contains("event: precio"), "precio");
        assertTrue(texto(salida).contains("data: {\"simbolo\":\"BTCUSDT\",\"precio\":83000.5,\"momento\":"));

        fuente.setError(new MercadoException("caída"));
        publicador.publicarPrecio(); // no lanza: se salta
    }

    @Test
    void desuscribirQuitaPorElNodoYEsSeguroRepetirlo() throws IOException {
        Suscriptor a = publicador.suscribir(new ByteArrayOutputStream());
        Suscriptor b = publicador.suscribir(new ByteArrayOutputStream());
        Suscriptor c = publicador.suscribir(new ByteArrayOutputStream());
        assertEquals(3, publicador.cantidadSuscriptores());
        assertTrue(publicador.desuscribir(b));      // el del medio, en O(1)
        assertFalse(publicador.desuscribir(b));     // dos veces: no pasa nada
        assertEquals(2, publicador.cantidadSuscriptores());
        assertTrue(publicador.desuscribir(a));
        assertTrue(publicador.desuscribir(c));
        assertEquals(0, publicador.cantidadSuscriptores());
    }

    @Test
    void quienFallaAlEscribirSeEliminaSolo() throws Exception {
        SalidaRota rota = new SalidaRota();
        Suscriptor caido = publicador.suscribir(rota);
        caido.activar();
        ByteArrayOutputStream sano = new ByteArrayOutputStream();
        publicador.suscribir(sano).activar();
        rota.rota = true;

        publicador.publicar("orden", Map.of("id", 1));
        esperarHasta(() -> publicador.cantidadSuscriptores() == 1, "que se quite al caído");
        assertTrue(caido.esperarCierre(1_000), "el hilo que lo atiende debe despertarse");
        esperarHasta(() -> texto(sano).contains("event: orden"), "el sano sigue recibiendo");
    }

    @Test
    void limiteDeConexionesResponde503() {
        publicador.suscribir(new ByteArrayOutputStream());
        publicador.suscribir(new ByteArrayOutputStream());
        Suscriptor tercero = publicador.suscribir(new ByteArrayOutputStream());
        ApiException e = assertThrows(ApiException.class, () -> publicador.suscribir(new ByteArrayOutputStream()));
        assertEquals(503, e.getCodigo());
        publicador.desuscribir(tercero);
        publicador.suscribir(new ByteArrayOutputStream()); // ya hay lugar
    }

    @Test
    void detenerCierraATodos() throws Exception {
        Suscriptor a = publicador.suscribir(new ByteArrayOutputStream());
        publicador.detener();
        assertTrue(a.esperarCierre(1_000));
        assertEquals(0, publicador.cantidadSuscriptores());
        assertThrows(IllegalArgumentException.class, () -> new Publicador(fuente, "BTCUSDT", 0));
    }
}
