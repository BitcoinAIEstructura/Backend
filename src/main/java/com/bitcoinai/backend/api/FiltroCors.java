package com.bitcoinai.backend.api;

import com.sun.net.httpserver.Filter;
import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpExchange;
import java.io.IOException;

/**
 * Agrega los encabezados CORS a todas las respuestas (también a los errores) y
 * contesta directamente las peticiones OPTIONS (preflight) con 204.
 */
class FiltroCors extends Filter {

    private final String origenPermitido;

    FiltroCors(String origenPermitido) {
        this.origenPermitido = origenPermitido;
    }

    @Override
    public void doFilter(HttpExchange intercambio, Chain cadena) throws IOException {
        Headers encabezados = intercambio.getResponseHeaders();
        encabezados.set("Access-Control-Allow-Origin", origenPermitido);
        encabezados.set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");
        encabezados.set("Access-Control-Allow-Headers", "Content-Type");
        encabezados.set("Access-Control-Max-Age", "86400");
        if (!"*".equals(origenPermitido)) {
            encabezados.set("Vary", "Origin");
        }
        if ("OPTIONS".equalsIgnoreCase(intercambio.getRequestMethod())) {
            intercambio.sendResponseHeaders(204, -1);
            return;
        }
        cadena.doFilter(intercambio);
    }

    @Override
    public String description() {
        return "CORS";
    }
}
