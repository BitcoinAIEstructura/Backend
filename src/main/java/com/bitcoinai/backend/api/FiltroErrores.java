package com.bitcoinai.backend.api;

import com.bitcoinai.backend.mercado.MercadoException;
import com.sun.net.httpserver.Filter;
import com.sun.net.httpserver.HttpExchange;
import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Convierte las excepciones en respuestas JSON:
 * <ul>
 *   <li>{@link ApiException} → su código y mensaje (404, 405, 400...).</li>
 *   <li>{@link MercadoException} → 502 "Fuente de mercado no disponible".</li>
 *   <li>Cualquier otra → 500 "Error interno del servidor".</li>
 * </ul>
 * Los detalles internos y las trazas solo van al registro del servidor, nunca al cliente.
 */
class FiltroErrores extends Filter {

    private static final Logger LOG = Logger.getLogger(FiltroErrores.class.getName());

    @Override
    public void doFilter(HttpExchange intercambio, Chain cadena) throws IOException {
        try {
            cadena.doFilter(intercambio);
        } catch (ApiException e) {
            responder(intercambio, e.getCodigo(), e.getMessage());
        } catch (MercadoException e) {
            LOG.warning("Fuente de mercado no disponible: " + e.getMessage());
            responder(intercambio, 502, "Fuente de mercado no disponible");
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error no controlado en " + intercambio.getRequestURI().getPath(), e);
            responder(intercambio, 500, "Error interno del servidor");
        }
    }

    /** Solo responde si todavía no se enviaron encabezados (getResponseCode() == -1). */
    private static void responder(HttpExchange intercambio, int codigo, String mensaje) throws IOException {
        if (intercambio.getResponseCode() == -1) {
            EscritorRespuesta.enviarError(intercambio, codigo, mensaje);
        }
    }

    @Override
    public String description() {
        return "Captura de errores";
    }
}
