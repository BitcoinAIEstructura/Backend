package com.bitcoinai.backend.api;

import com.bitcoinai.backend.util.JsonEscritor;
import com.sun.net.httpserver.HttpExchange;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/** Escribe respuestas JSON en un HttpExchange. */
final class EscritorRespuesta {

    static final String TIPO_JSON = "application/json; charset=utf-8";

    private EscritorRespuesta() {
    }

    /** Escribe el cuerpo como JSON con el código dado. Convierte a texto antes de enviar encabezados. */
    static void enviarJson(HttpExchange intercambio, int codigo, Object cuerpo) throws IOException {
        byte[] bytes = JsonEscritor.escribir(cuerpo).getBytes(StandardCharsets.UTF_8);
        intercambio.getResponseHeaders().set("Content-Type", TIPO_JSON);
        intercambio.sendResponseHeaders(codigo, bytes.length);
        try (OutputStream salida = intercambio.getResponseBody()) {
            salida.write(bytes);
        }
    }

    /** Escribe {"error": mensaje} con el código dado. */
    static void enviarError(HttpExchange intercambio, int codigo, String mensaje) throws IOException {
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("error", mensaje);
        enviarJson(intercambio, codigo, cuerpo);
    }
}
