package com.bitcoinai.backend.persistencia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.simulacion.AlmacenSimulacion;
import com.bitcoinai.backend.simulacion.DatosCartera;
import com.bitcoinai.backend.simulacion.EstadoOrden;
import com.bitcoinai.backend.simulacion.EstadoSimulacion;
import com.bitcoinai.backend.simulacion.Evento;
import com.bitcoinai.backend.simulacion.Orden;
import com.bitcoinai.backend.util.JsonEscritor;
import com.bitcoinai.backend.util.JsonLector;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.FileSystemException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.logging.Logger;

/**
 * Guarda el estado de la simulación en tres archivos JSON dentro de un directorio
 * (variable de entorno {@code DATA_DIR}, por defecto {@code ./data}):
 * <ul>
 *   <li>{@value #CARTERA}: saldo, BTC y costo de la posición.</li>
 *   <li>{@value #ORDENES}: cola de pendientes (en orden de llegada), registro,
 *       ids en orden de creación (para deshacer) y el próximo id.</li>
 *   <li>{@value #HISTORIAL}: eventos del más viejo al más nuevo.</li>
 * </ul>
 *
 * <p><b>Escritura atómica:</b> cada archivo se escribe primero en uno temporal
 * ({@code .tmp}) y luego se mueve sobre el definitivo. Si el proceso muere a mitad
 * de una escritura, queda el archivo anterior completo, nunca uno a medias.
 *
 * <p><b>Carga tolerante:</b> si un archivo está dañado, se aparta con otro nombre
 * ({@code .danado-<momento>}) para poder revisarlo, se registra una advertencia y
 * se empieza limpio. Cartera y órdenes se cargan juntas (si una falla, ninguna se
 * usa, para no mezclar estados incoherentes); el historial va aparte.
 *
 * <p>Nota: el disco de un contenedor de Railway se borra en cada despliegue; para
 * conservar los datos hay que montar un volumen y apuntar {@code DATA_DIR} a él.
 */
public class AlmacenArchivos implements AlmacenSimulacion {

    /** Nombre del archivo de la cartera. */
    public static final String CARTERA = "cartera.json";
    /** Nombre del archivo de las órdenes. */
    public static final String ORDENES = "ordenes.json";
    /** Nombre del archivo del historial. */
    public static final String HISTORIAL = "historial.json";

    private static final int VERSION = 1;
    private static final int INTENTOS_AL_MOVER = 5;
    private static final Logger LOG = Logger.getLogger(AlmacenArchivos.class.getName());

    private final Path directorio;

    /**
     * Crea el almacén.
     *
     * @param directorio carpeta donde guardar (se crea si no existe)
     */
    public AlmacenArchivos(Path directorio) {
        this.directorio = Objects.requireNonNull(directorio, "directorio");
    }

    /**
     * Devuelve la carpeta donde guarda.
     *
     * @return la carpeta
     */
    public Path getDirectorio() {
        return directorio;
    }

    // ---------- guardar ----------

    /**
     * Guarda los tres archivos de forma atómica cada uno.
     * Complejidad: O(n) en el tamaño del estado.
     *
     * @param estado foto del libro de órdenes
     * @throws UncheckedIOException si no se pudo escribir
     */
    @Override
    public void guardar(EstadoSimulacion estado) {
        try {
            Files.createDirectories(directorio);

            Map<String, Object> ordenes = new LinkedHashMap<>();
            ordenes.put("version", VERSION);
            ordenes.put("siguienteId", estado.siguienteId());
            ordenes.put("pendientes", estado.pendientes());
            ordenes.put("registro", estado.registro());
            ordenes.put("creadas", estado.creadas());
            escribirAtomico(ORDENES, ordenes);

            Map<String, Object> cartera = new LinkedHashMap<>();
            cartera.put("version", VERSION);
            cartera.put("cartera", estado.cartera());
            escribirAtomico(CARTERA, cartera);

            Map<String, Object> historial = new LinkedHashMap<>();
            historial.put("version", VERSION);
            historial.put("eventos", estado.eventos());
            escribirAtomico(HISTORIAL, historial);
        } catch (IOException e) {
            throw new UncheckedIOException("No se pudo guardar en " + directorio, e);
        }
    }

    /** Escribe en un temporal y lo mueve sobre el definitivo. */
    private void escribirAtomico(String nombre, Object contenido) throws IOException {
        Path destino = directorio.resolve(nombre);
        Path temporal = directorio.resolve(nombre + ".tmp");
        Files.writeString(temporal, JsonEscritor.escribir(contenido), StandardCharsets.UTF_8);
        for (int intento = 1; ; intento++) {
            try {
                Files.move(temporal, destino, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
                return;
            } catch (AtomicMoveNotSupportedException e) {
                Files.move(temporal, destino, StandardCopyOption.REPLACE_EXISTING);
                return;
            } catch (FileSystemException e) {
                // En Windows otro programa (antivirus, OneDrive) puede tener el archivo abierto un instante.
                if (intento >= INTENTOS_AL_MOVER) {
                    throw e;
                }
                esperar(20L * intento);
            }
        }
    }

    // ---------- cargar ----------

    /**
     * Carga el estado guardado. Nunca falla: si algo está dañado lo aparta,
     * registra una advertencia y lo trata como si no existiera.
     *
     * @return el estado, o vacío si no había nada utilizable
     */
    @Override
    public Optional<EstadoSimulacion> cargar() {
        DatosCartera cartera = null;
        long siguienteId = 1;
        Lista<Orden> pendientes = new Lista<>();
        Lista<Orden> registro = new Lista<>();
        Lista<Long> creadas = new Lista<>();

        boolean hayCartera = Files.exists(directorio.resolve(CARTERA));
        boolean hayOrdenes = Files.exists(directorio.resolve(ORDENES));
        if (hayCartera || hayOrdenes) {
            try {
                if (!hayCartera || !hayOrdenes) {
                    throw new DatosDanadosException("falta " + (hayCartera ? ORDENES : CARTERA)
                            + " y no se puede usar el otro solo");
                }
                Map<String, Object> raizCartera = leer(CARTERA);
                Map<String, Object> raizOrdenes = leer(ORDENES);
                cartera = ConversorJson.cartera(raizCartera.get("cartera"));
                siguienteId = ConversorJson.entero(raizOrdenes, "siguienteId");
                for (Object o : ConversorJson.lista(raizOrdenes, "pendientes")) {
                    Orden orden = ConversorJson.orden(o);
                    if (orden.estado() != EstadoOrden.PENDIENTE) {
                        throw new DatosDanadosException("la orden #" + orden.id() + " está en la cola sin estar pendiente");
                    }
                    pendientes.agregar(orden);
                }
                for (Object o : ConversorJson.lista(raizOrdenes, "registro")) {
                    registro.agregar(ConversorJson.orden(o));
                }
                for (Object o : ConversorJson.lista(raizOrdenes, "creadas")) {
                    if (!(o instanceof Double id) || id != Math.rint(id) || id < 1) {
                        throw new DatosDanadosException("id inválido en 'creadas': " + o);
                    }
                    creadas.agregar(id.longValue());
                }
            } catch (IOException | RuntimeException e) {
                LOG.warning("Cartera y órdenes guardadas inutilizables (" + e.getMessage()
                        + "); se empieza con cartera y órdenes limpias.");
                apartar(CARTERA);
                apartar(ORDENES);
                cartera = null;
                siguienteId = 1;
                pendientes = new Lista<>();
                registro = new Lista<>();
                creadas = new Lista<>();
            }
        }

        Lista<Evento> eventos = new Lista<>();
        if (Files.exists(directorio.resolve(HISTORIAL))) {
            try {
                for (Object o : ConversorJson.lista(leer(HISTORIAL), "eventos")) {
                    eventos.agregar(ConversorJson.evento(o));
                }
            } catch (IOException | RuntimeException e) {
                LOG.warning("Historial guardado inutilizable (" + e.getMessage() + "); se empieza sin historial.");
                apartar(HISTORIAL);
                eventos = new Lista<>();
            }
        }

        if (cartera == null && eventos.estaVacia()) {
            return Optional.empty();
        }
        return Optional.of(new EstadoSimulacion(cartera, siguienteId, pendientes, registro, creadas, eventos));
    }

    /** Lee y valida la cabecera de un archivo. */
    private Map<String, Object> leer(String nombre) throws IOException {
        String texto = Files.readString(directorio.resolve(nombre), StandardCharsets.UTF_8);
        Map<String, Object> raiz = ConversorJson.mapa(JsonLector.leer(texto), nombre);
        if (ConversorJson.entero(raiz, "version") != VERSION) {
            throw new DatosDanadosException(nombre + " tiene una versión desconocida");
        }
        return raiz;
    }

    /** Renombra un archivo dañado para no perderlo ni volver a leerlo. */
    private void apartar(String nombre) {
        Path archivo = directorio.resolve(nombre);
        if (!Files.exists(archivo)) {
            return;
        }
        Path apartado = directorio.resolve(nombre + ".danado-" + System.currentTimeMillis());
        try {
            Files.move(archivo, apartado, StandardCopyOption.REPLACE_EXISTING);
            LOG.warning("Archivo dañado apartado como " + apartado.getFileName());
        } catch (IOException e) {
            LOG.warning("No se pudo apartar " + archivo + ": " + e.getMessage());
        }
    }

    private static void esperar(long milisegundos) {
        try {
            Thread.sleep(milisegundos);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
