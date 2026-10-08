package com.bitcoinai.backend.api;

import com.bitcoinai.backend.util.JsonLector;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

/** Utilidades para llamar al servidor de pruebas con java.net.http.HttpClient. */
final class ClienteHttpPrueba {

    private static final HttpClient HTTP = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(2))
            .build();

    private ClienteHttpPrueba() {
    }

    static HttpResponse<String> pedir(int puerto, String metodo, String rutaYConsulta) {
        return enviar(puerto, metodo, rutaYConsulta, null);
    }

    /** Petición con cuerpo JSON (o sin cuerpo si es null). */
    static HttpResponse<String> enviar(int puerto, String metodo, String rutaYConsulta, String cuerpo) {
        HttpRequest peticion = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + puerto + rutaYConsulta))
                .timeout(Duration.ofSeconds(5))
                .header("Content-Type", "application/json")
                .method(metodo, cuerpo == null
                        ? HttpRequest.BodyPublishers.noBody()
                        : HttpRequest.BodyPublishers.ofString(cuerpo))
                .build();
        try {
            return HTTP.send(peticion, HttpResponse.BodyHandlers.ofString());
        } catch (IOException e) {
            throw new RuntimeException(e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        }
    }

    static HttpResponse<String> get(int puerto, String rutaYConsulta) {
        return pedir(puerto, "GET", rutaYConsulta);
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> json(HttpResponse<String> respuesta) {
        return (Map<String, Object>) JsonLector.leer(respuesta.body());
    }
}
