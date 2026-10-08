package com.bitcoinai.backend.api;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import java.io.IOException;
import java.util.Locale;
import java.util.Objects;

/**
 * Atiende {@code GET /api/stream}: deja la conexión abierta y la registra en el
 * {@link Publicador}, que le irá escribiendo los eventos.
 *
 * <p>El hilo (virtual) de la petición se queda esperando hasta que el
 * suscriptor se cierra: porque el cliente se fue (falla una escritura) o porque
 * el servidor se apaga. Entonces lo quita de la lista y termina.
 */
class ManejadorStream implements HttpHandler {

    static final String RUTA = "/api/stream";

    private final Publicador publicador;

    ManejadorStream(Publicador publicador) {
        this.publicador = Objects.requireNonNull(publicador, "publicador");
    }

    @Override
    public void handle(HttpExchange intercambio) throws IOException {
        String ruta = intercambio.getRequestURI().getPath();
        if (!RUTA.equals(ruta) && !(RUTA + "/").equals(ruta)) {
            throw new ApiException(404, "Ruta no encontrada: " + ruta);
        }
        if (!"GET".equals(intercambio.getRequestMethod().toUpperCase(Locale.ROOT))) {
            intercambio.getResponseHeaders().set("Allow", "GET");
            throw new ApiException(405, "Método " + intercambio.getRequestMethod() + " no permitido en " + RUTA + "; use GET");
        }

        Suscriptor suscriptor = publicador.suscribir(intercambio.getResponseBody()); // 503 si está lleno
        try {
            Headers encabezados = intercambio.getResponseHeaders();
            encabezados.set("Content-Type", "text/event-stream; charset=utf-8");
            encabezados.set("Cache-Control", "no-cache");
            encabezados.set("X-Accel-Buffering", "no"); // que los proxies no acumulen los eventos
            intercambio.sendResponseHeaders(200, 0);    // 0 = cuerpo de largo indefinido (por partes)
            suscriptor.activar();
            suscriptor.esperarCierre();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (IOException e) {
            // el cliente se fue antes de terminar de conectarse
        } finally {
            publicador.desuscribir(suscriptor);
        }
    }
}
