package com.bitcoinai.backend.api;

import com.sun.net.httpserver.Filter;
import com.sun.net.httpserver.HttpExchange;
import java.io.IOException;
import java.util.logging.Logger;

/**
 * Registra cada petición en una línea: método, ruta, código y milisegundos.
 * Es el filtro más externo, así mide el tiempo total, y cierra el intercambio al final.
 */
class FiltroRegistro extends Filter {

    private static final Logger LOG = Logger.getLogger(FiltroRegistro.class.getName());

    @Override
    public void doFilter(HttpExchange intercambio, Chain cadena) throws IOException {
        long inicio = System.nanoTime();
        try {
            cadena.doFilter(intercambio);
        } finally {
            long milisegundos = (System.nanoTime() - inicio) / 1_000_000;
            LOG.info(intercambio.getRequestMethod() + " " + intercambio.getRequestURI().getPath()
                    + " " + intercambio.getResponseCode() + " " + milisegundos + " ms");
            intercambio.close();
        }
    }

    @Override
    public String description() {
        return "Registro de peticiones";
    }
}
