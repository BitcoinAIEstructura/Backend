package com.bitcoinai.backend;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.api.Configuracion;
import com.bitcoinai.backend.api.Servidor;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class MainTest {

    @Test
    void iniciarArrancaElServidorConHealthDisponible(@TempDir Path datos) throws Exception {
        Configuracion config = Configuracion.desde(Map.of("PORT", "0", "DATA_DIR", datos.toString())::get);
        Main.Aplicacion aplicacion = Main.iniciar(config, "127.0.0.1");
        Servidor servidor = aplicacion.servidor();
        try {
            HttpClient cliente = HttpClient.newHttpClient();
            HttpResponse<String> r = cliente.send(
                    HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + servidor.puerto() + "/health")).build(),
                    HttpResponse.BodyHandlers.ofString());
            assertEquals(200, r.statusCode());
            assertEquals("{\"estado\":\"ok\"}", r.body());
            // Las rutas de la simulación también quedan registradas; el bot arranca detenido.
            HttpResponse<String> bot = cliente.send(
                    HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + servidor.puerto() + "/api/bot/estado")).build(),
                    HttpResponse.BodyHandlers.ofString());
            assertEquals(200, bot.statusCode());
            assertFalse(aplicacion.bot().estado().activo());
        } finally {
            aplicacion.detener();
        }
    }

    @Test
    void laSimulacionSobreviveAUnReinicio(@TempDir Path datos) throws Exception {
        Configuracion config = Configuracion.desde(Map.of("PORT", "0", "DATA_DIR", datos.toString())::get);
        Main.Aplicacion primera = Main.iniciar(config, "127.0.0.1");
        try {
            primera.libro().crearCompra(100, "antes del reinicio");
            primera.libro().crearCompra(200, null);
        } finally {
            primera.detener();
        }
        assertTrue(Files.exists(datos.resolve("ordenes.json")));

        Main.Aplicacion segunda = Main.iniciar(config, "127.0.0.1");
        try {
            assertEquals(2, segunda.libro().cantidadPendientes());
            assertEquals("antes del reinicio", segunda.libro().obtener(1).motivo());
            assertEquals(3, segunda.libro().crearCompra(50, null).id());
        } finally {
            segunda.detener();
        }
    }
}
