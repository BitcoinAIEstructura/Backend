package com.bitcoinai.backend.api;

import com.bitcoinai.backend.estructuras.NodoDoble;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Un cliente conectado a {@code /api/stream}.
 *
 * <p>Guarda el nodo de la {@code ListaDoble} donde está registrado, para que el
 * {@link Publicador} lo quite en O(1) cuando se desconecta, sin buscarlo.
 * Las escrituras están sincronizadas porque el latido y los eventos pueden
 * llegar desde hilos distintos.
 */
public final class Suscriptor {

    private static final AtomicLong CONTADOR = new AtomicLong();

    private final long id = CONTADOR.incrementAndGet();
    private final OutputStream salida;
    private final CountDownLatch cerrado = new CountDownLatch(1);
    private boolean activo;   // protegido por "this"
    private boolean terminado; // protegido por "this"

    /** Nodo de la lista de suscriptores que lo contiene; lo asigna el Publicador. */
    NodoDoble<Suscriptor> nodo;

    Suscriptor(OutputStream salida) {
        this.salida = salida;
    }

    /**
     * Devuelve un número que identifica al suscriptor.
     *
     * @return el id
     */
    public long getId() {
        return id;
    }

    /**
     * Marca el suscriptor como listo (los encabezados HTTP ya se enviaron) y
     * escribe el saludo inicial. Antes de esto, los eventos se descartan.
     *
     * @throws IOException si el cliente ya no está
     */
    synchronized void activar() throws IOException {
        activo = true;
        escribir("retry: 5000\n: conectado\n\n");
    }

    /**
     * Envía texto SSE ya formateado. Si todavía no está activo o ya terminó, no hace nada.
     *
     * @param texto bloque SSE terminado en línea vacía
     * @throws IOException si falla la escritura (el cliente se desconectó)
     */
    synchronized void enviar(String texto) throws IOException {
        if (activo && !terminado) {
            escribir(texto);
        }
    }

    private void escribir(String texto) throws IOException {
        salida.write(texto.getBytes(StandardCharsets.UTF_8));
        salida.flush();
    }

    /** Marca el suscriptor como terminado y despierta al hilo que espera en {@link #esperarCierre()}. */
    void cerrar() {
        synchronized (this) {
            terminado = true;
        }
        cerrado.countDown();
    }

    /**
     * Bloquea el hilo hasta que el suscriptor se cierre.
     *
     * @throws InterruptedException si interrumpen el hilo
     */
    void esperarCierre() throws InterruptedException {
        cerrado.await();
    }

    /** Espera el cierre como máximo el tiempo dado. Devuelve true si se cerró. */
    boolean esperarCierre(long milisegundos) throws InterruptedException {
        return cerrado.await(milisegundos, TimeUnit.MILLISECONDS);
    }
}
