package com.bitcoinai.backend.api;

import com.sun.net.httpserver.HttpContext;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Servidor HTTP del backend sobre {@code com.sun.net.httpserver}, con un hilo
 * virtual por petición.
 *
 * <p>Filtros, de afuera hacia adentro: registro → CORS → captura de errores → {@link Router}.
 */
public class Servidor {

    private final HttpServer http;
    private final ExecutorService ejecutor;
    private final AtomicBoolean detenido = new AtomicBoolean();
    private final String origenPermitido;

    /**
     * Crea el servidor (todavía sin escuchar).
     *
     * @param host            dirección donde escuchar; "0.0.0.0" para todas las interfaces
     * @param puerto          puerto; 0 elige uno libre
     * @param router          rutas de la API
     * @param origenPermitido valor de Access-Control-Allow-Origin
     * @throws IOException si no se puede abrir el puerto
     */
    public Servidor(String host, int puerto, Router router, String origenPermitido) throws IOException {
        this.origenPermitido = origenPermitido;
        http = HttpServer.create(new InetSocketAddress(host, puerto), 0);
        agregarContexto("/", router);
        ejecutor = Executors.newVirtualThreadPerTaskExecutor();
        http.setExecutor(ejecutor);
    }

    /**
     * Habilita {@code GET /api/stream} (Server-Sent Events) con el publicador dado.
     * Usa los mismos filtros que el resto de la API.
     *
     * @param publicador quien envía los eventos a los clientes conectados
     */
    public void agregarStream(Publicador publicador) {
        agregarContexto(ManejadorStream.RUTA, new ManejadorStream(publicador));
    }

    /** Registra un manejador para una ruta (y todo lo que empiece por ella) con los filtros comunes. */
    private void agregarContexto(String ruta, HttpHandler manejador) {
        HttpContext contexto = http.createContext(ruta, manejador);
        contexto.getFilters().add(new FiltroRegistro());
        contexto.getFilters().add(new FiltroCors(origenPermitido));
        contexto.getFilters().add(new FiltroErrores());
    }

    /** Empieza a aceptar peticiones. */
    public void iniciar() {
        http.start();
    }

    /**
     * Devuelve el puerto real (útil cuando se pidió el 0).
     *
     * @return el puerto donde escucha
     */
    public int puerto() {
        return http.getAddress().getPort();
    }

    /**
     * Deja de aceptar peticiones y espera hasta {@code segundosEspera} a que
     * terminen las que están en curso. Llamarlo más de una vez no hace nada.
     *
     * @param segundosEspera tiempo máximo de espera
     */
    public void detener(int segundosEspera) {
        if (detenido.compareAndSet(false, true)) {
            http.stop(segundosEspera);
            ejecutor.shutdown();
        }
    }
}
