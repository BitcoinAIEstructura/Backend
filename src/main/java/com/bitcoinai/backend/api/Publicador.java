package com.bitcoinai.backend.api;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.mercado.FuenteDeMercado;
import com.bitcoinai.backend.simulacion.PublicadorEventos;
import com.bitcoinai.backend.util.JsonEscritor;
import java.io.IOException;
import java.io.OutputStream;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Logger;

/**
 * Publica eventos en tiempo real a los clientes de {@code /api/stream} con
 * Server-Sent Events (SSE).
 *
 * <p>Cada evento se envía así:
 * <pre>
 * event: precio
 * data: {"simbolo":"BTCUSDT","precio":83097.08,"momento":1791417600000}
 *
 * </pre>
 * Eventos: {@code precio} (cada 5 s), {@code orden}, {@code cartera} y {@code senal}
 * (los publican el libro de órdenes y el bot a través de la interfaz
 * {@link PublicadorEventos}), más un comentario de latido ({@code : latido}) cada
 * 15 s para que los proxies no corten la conexión por inactividad.
 *
 * <p><b>Uso de la lista doble:</b> los suscriptores están en una
 * {@code ListaDoble<Suscriptor>}. Al agregar uno se guarda su nodo
 * ({@code agregarFinalNodo}); cuando se desconecta o falla al escribirle, se
 * quita con {@code eliminarNodo(nodo)} en O(1): el nodo ya conoce a su anterior y
 * a su siguiente, así que basta con unirlos, sin recorrer la lista para buscarlo.
 * Con una lista simple habría que recorrerla para hallar el nodo anterior (O(n)).
 *
 * <p>Concurrencia: la lista la protege un {@link ReentrantLock}. Los envíos los
 * hace un solo hilo dedicado, así {@link #publicar} nunca bloquea a quien lo
 * llama (el libro de órdenes lo llama con su candado tomado) y los eventos
 * llegan en orden.
 */
public class Publicador implements PublicadorEventos {

    /** Límite por defecto de conexiones simultáneas. */
    public static final int MAXIMO_POR_DEFECTO = 50;

    private static final Logger LOG = Logger.getLogger(Publicador.class.getName());

    private final FuenteDeMercado fuente;
    private final String simbolo;
    private final int maximo;
    private final Duration periodoPrecio;
    private final Duration periodoLatido;

    private final ListaDoble<Suscriptor> suscriptores = new ListaDoble<>();
    private final ReentrantLock candado = new ReentrantLock();
    private final ExecutorService envios = Executors.newSingleThreadExecutor(hilo("sse-envios"));
    private ScheduledExecutorService planificador; // protegido por "this"

    /**
     * Publicador con precio cada 5 s y latido cada 15 s.
     *
     * @param fuente  de dónde sale el precio
     * @param simbolo par, por ejemplo "BTCUSDT"
     * @param maximo  conexiones simultáneas permitidas ({@code MAX_STREAMS})
     */
    public Publicador(FuenteDeMercado fuente, String simbolo, int maximo) {
        this(fuente, simbolo, maximo, Duration.ofSeconds(5), Duration.ofSeconds(15));
    }

    /**
     * Crea el publicador (con periodos configurables, útil en pruebas).
     *
     * @param fuente        de dónde sale el precio
     * @param simbolo       par
     * @param maximo        conexiones simultáneas permitidas (1 o más)
     * @param periodoPrecio cada cuánto se publica el precio
     * @param periodoLatido cada cuánto se envía el latido
     */
    public Publicador(FuenteDeMercado fuente, String simbolo, int maximo, Duration periodoPrecio, Duration periodoLatido) {
        if (maximo < 1) {
            throw new IllegalArgumentException("El máximo de conexiones debe ser al menos 1");
        }
        this.fuente = Objects.requireNonNull(fuente, "fuente");
        this.simbolo = Objects.requireNonNull(simbolo, "simbolo");
        this.maximo = maximo;
        this.periodoPrecio = Objects.requireNonNull(periodoPrecio, "periodoPrecio");
        this.periodoLatido = Objects.requireNonNull(periodoLatido, "periodoLatido");
    }

    /** Empieza a publicar el precio y el latido periódicamente. */
    public synchronized void iniciar() {
        if (planificador != null) {
            return;
        }
        planificador = Executors.newSingleThreadScheduledExecutor(hilo("sse-planificador"));
        planificador.scheduleAtFixedRate(this::publicarPrecio, periodoPrecio.toMillis(),
                periodoPrecio.toMillis(), TimeUnit.MILLISECONDS);
        planificador.scheduleAtFixedRate(this::enviarLatido, periodoLatido.toMillis(),
                periodoLatido.toMillis(), TimeUnit.MILLISECONDS);
    }

    /** Detiene las tareas y cierra todas las conexiones (para apagar el servidor). */
    public synchronized void detener() {
        if (planificador != null) {
            planificador.shutdownNow();
            planificador = null;
        }
        envios.shutdown();
        candado.lock();
        try {
            for (Suscriptor suscriptor : suscriptores) {
                suscriptor.cerrar();
            }
            suscriptores.vaciar();
        } finally {
            candado.unlock();
        }
    }

    // ---------- suscriptores ----------

    /**
     * Registra un cliente nuevo. Queda inactivo hasta que se llame a
     * {@code activar()} (después de enviar los encabezados).
     * Complejidad: O(1).
     *
     * @param salida cuerpo de la respuesta HTTP
     * @return el suscriptor
     * @throws ApiException 503 si ya se alcanzó el máximo de conexiones
     */
    public Suscriptor suscribir(OutputStream salida) {
        Suscriptor suscriptor = new Suscriptor(salida);
        candado.lock();
        try {
            if (suscriptores.tamanio() >= maximo) {
                throw new ApiException(503, "Demasiadas conexiones de tiempo real abiertas (máximo "
                        + maximo + "); intenta más tarde");
            }
            suscriptor.nodo = suscriptores.agregarFinalNodo(suscriptor);
        } finally {
            candado.unlock();
        }
        return suscriptor;
    }

    /**
     * Quita un suscriptor usando su nodo, sin recorrer la lista, y lo cierra.
     * Llamarlo más de una vez es seguro.
     * Complejidad: O(1).
     *
     * @param suscriptor el suscriptor
     * @return true si estaba en la lista
     */
    public boolean desuscribir(Suscriptor suscriptor) {
        boolean quitado;
        candado.lock();
        try {
            quitado = suscriptores.eliminarNodo(suscriptor.nodo);
        } finally {
            candado.unlock();
        }
        suscriptor.cerrar();
        return quitado;
    }

    /**
     * Devuelve cuántos clientes están conectados.
     *
     * @return la cantidad
     */
    public int cantidadSuscriptores() {
        candado.lock();
        try {
            return suscriptores.tamanio();
        } finally {
            candado.unlock();
        }
    }

    // ---------- publicación ----------

    /**
     * Encola un evento para todos los clientes. No bloquea: lo envía el hilo de envíos.
     *
     * @param tipo  nombre del evento ("precio", "orden", "cartera", "senal")
     * @param datos datos que se escriben como JSON en la línea {@code data}
     */
    @Override
    public void publicar(String tipo, Object datos) {
        String texto = "event: " + tipo + "\ndata: " + JsonEscritor.escribir(datos) + "\n\n";
        encolar(texto);
    }

    /** Envía un comentario de latido (las líneas que empiezan con ":" el navegador las ignora). */
    void enviarLatido() {
        encolar(": latido\n\n");
    }

    /** Publica el precio actual, solo si hay alguien escuchando. Si la fuente falla, lo salta. */
    void publicarPrecio() {
        if (cantidadSuscriptores() == 0) {
            return;
        }
        try {
            Map<String, Object> datos = new LinkedHashMap<>();
            datos.put("simbolo", simbolo);
            datos.put("precio", fuente.obtenerPrecioActual(simbolo));
            datos.put("momento", System.currentTimeMillis());
            publicar("precio", datos);
        } catch (RuntimeException e) {
            LOG.fine("No se pudo publicar el precio: " + e.getMessage());
        }
    }

    private void encolar(String texto) {
        try {
            envios.execute(() -> difundir(texto));
        } catch (RejectedExecutionException e) {
            // el publicador se está apagando
        }
    }

    /**
     * Escribe a todos. Se copia la lista con el candado tomado (O(n)) y se escribe
     * sin él, para que un cliente lento no bloquee las altas y bajas. A quien
     * falle se lo quita por su nodo en O(1).
     */
    private void difundir(String texto) {
        Lista<Suscriptor> copia = new Lista<>();
        candado.lock();
        try {
            for (Suscriptor suscriptor : suscriptores) {
                copia.agregar(suscriptor);
            }
        } finally {
            candado.unlock();
        }
        for (Suscriptor suscriptor : copia) {
            try {
                suscriptor.enviar(texto);
            } catch (IOException e) {
                desuscribir(suscriptor); // el cliente se fue
            }
        }
    }

    private static ThreadFactory hilo(String nombre) {
        return tarea -> {
            Thread hilo = new Thread(tarea, nombre);
            hilo.setDaemon(true);
            return hilo;
        };
    }
}
