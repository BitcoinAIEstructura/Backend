package com.bitcoinai.backend.api;

import com.bitcoinai.backend.estructuras.Lista;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

/**
 * Enrutador propio: asocia método y ruta con un {@link Manejador}.
 *
 * <ul>
 *   <li>Rutas exactas ("/api/cartera") y con parámetros ("/api/ordenes/{id}"):
 *       cada {@code {nombre}} acepta un segmento y su valor llega en
 *       {@link Peticion#parametrosRuta()}. Una ruta exacta tiene prioridad sobre
 *       una con parámetros ("/api/ordenes/procesar" no se confunde con un id).</li>
 *   <li>Ruta desconocida → 404.</li>
 *   <li>Ruta conocida con otro método → 405 y encabezado {@code Allow}.</li>
 *   <li>Una barra final se ignora: "/health/" es igual a "/health".</li>
 *   <li>El cuerpo de la petición se lee como texto UTF-8, hasta {@value #TAMANIO_MAXIMO_CUERPO} bytes (si no, 413).</li>
 * </ul>
 * Los errores se lanzan como {@link ApiException} y los convierte en JSON el
 * filtro de errores. Una ruta exacta se encuentra en O(1) promedio (tabla hash);
 * las rutas con parámetros se prueban una por una, O(p · s) con p patrones de s segmentos.
 */
public class Router implements HttpHandler {

    /** Tamaño máximo del cuerpo de una petición, en bytes. */
    public static final int TAMANIO_MAXIMO_CUERPO = 64 * 1024;

    /** Ruta con parámetros: sus segmentos y sus manejadores por método. */
    private record RutaConParametros(String patron, String[] segmentos, Map<String, Manejador> porMetodo) {

        /** Devuelve los parámetros si la ruta coincide con el patrón, o null si no. */
        Map<String, String> coincidir(String ruta) {
            String[] partes = ruta.split("/", -1);
            if (partes.length != segmentos.length) {
                return null;
            }
            Map<String, String> parametros = new LinkedHashMap<>();
            for (int i = 0; i < partes.length; i++) {
                String segmento = segmentos[i];
                if (segmento.startsWith("{") && segmento.endsWith("}")) {
                    if (partes[i].isEmpty()) {
                        return null;
                    }
                    parametros.put(segmento.substring(1, segmento.length() - 1), partes[i]);
                } else if (!segmento.equals(partes[i])) {
                    return null;
                }
            }
            return Collections.unmodifiableMap(parametros);
        }
    }

    /** ruta exacta → (método → manejador), en orden de registro. */
    private final Map<String, Map<String, Manejador>> rutas = new LinkedHashMap<>();
    /** Rutas con parámetros, en orden de registro. */
    private final Lista<RutaConParametros> rutasConParametros = new Lista<>();

    /**
     * Registra un manejador.
     *
     * @param metodo    método HTTP, por ejemplo "GET"
     * @param ruta      ruta exacta ("/api/velas") o con parámetros ("/api/ordenes/{id}")
     * @param manejador quién atiende la ruta
     * @return este mismo enrutador, para encadenar llamadas
     * @throws IllegalArgumentException si la ruta ya tiene un manejador para ese método
     */
    public Router agregar(String metodo, String ruta, Manejador manejador) {
        Objects.requireNonNull(manejador, "manejador");
        String metodoNormalizado = metodo.toUpperCase(Locale.ROOT);
        String rutaNormalizada = normalizar(ruta);
        Map<String, Manejador> porMetodo;
        if (rutaNormalizada.contains("{")) {
            porMetodo = buscarPatron(rutaNormalizada);
            if (porMetodo == null) {
                porMetodo = new LinkedHashMap<>();
                rutasConParametros.agregar(new RutaConParametros(rutaNormalizada,
                        rutaNormalizada.split("/", -1), porMetodo));
            }
        } else {
            porMetodo = rutas.computeIfAbsent(rutaNormalizada, r -> new LinkedHashMap<>());
        }
        if (porMetodo.putIfAbsent(metodoNormalizado, manejador) != null) {
            throw new IllegalArgumentException("Ruta duplicada: " + metodoNormalizado + " " + ruta);
        }
        return this;
    }

    /**
     * Atajo para registrar una ruta GET.
     *
     * @param ruta      ruta
     * @param manejador quién atiende la ruta
     * @return este mismo enrutador
     */
    public Router get(String ruta, Manejador manejador) {
        return agregar("GET", ruta, manejador);
    }

    /**
     * Atajo para registrar una ruta POST.
     *
     * @param ruta      ruta
     * @param manejador quién atiende la ruta
     * @return este mismo enrutador
     */
    public Router post(String ruta, Manejador manejador) {
        return agregar("POST", ruta, manejador);
    }

    /**
     * Atajo para registrar una ruta DELETE.
     *
     * @param ruta      ruta
     * @param manejador quién atiende la ruta
     * @return este mismo enrutador
     */
    public Router delete(String ruta, Manejador manejador) {
        return agregar("DELETE", ruta, manejador);
    }

    /**
     * Atiende una petición del servidor HTTP: busca el manejador y escribe su respuesta.
     *
     * @param intercambio la petición y respuesta HTTP
     * @throws IOException si falla la lectura o la escritura
     * @throws ApiException con 404, 405 o 413 si corresponde
     */
    @Override
    public void handle(HttpExchange intercambio) throws IOException {
        String ruta = normalizar(intercambio.getRequestURI().getPath());
        String metodo = intercambio.getRequestMethod().toUpperCase(Locale.ROOT);

        Map<String, Manejador> porMetodo = rutas.get(ruta);
        Map<String, String> parametrosRuta = Map.of();
        if (porMetodo == null) {
            for (RutaConParametros patron : rutasConParametros) {
                Map<String, String> coincidencia = patron.coincidir(ruta);
                if (coincidencia != null) {
                    porMetodo = patron.porMetodo();
                    parametrosRuta = coincidencia;
                    break;
                }
            }
        }
        if (porMetodo == null) {
            throw new ApiException(404, "Ruta no encontrada: " + ruta);
        }
        Manejador manejador = porMetodo.get(metodo);
        if (manejador == null) {
            String permitidos = String.join(", ", porMetodo.keySet());
            intercambio.getResponseHeaders().set("Allow", permitidos);
            throw new ApiException(405, "Método " + metodo + " no permitido en " + ruta + "; use " + permitidos);
        }

        Peticion peticion = new Peticion(metodo, ruta,
                Peticion.leerConsulta(intercambio.getRequestURI().getRawQuery()),
                parametrosRuta, leerCuerpo(intercambio));
        Respuesta respuesta = manejador.manejar(peticion);
        EscritorRespuesta.enviarJson(intercambio, respuesta.codigo(), respuesta.cuerpo());
    }

    private Map<String, Manejador> buscarPatron(String patron) {
        for (RutaConParametros ruta : rutasConParametros) {
            if (ruta.patron().equals(patron)) {
                return ruta.porMetodo();
            }
        }
        return null;
    }

    private static String leerCuerpo(HttpExchange intercambio) throws IOException {
        try (InputStream entrada = intercambio.getRequestBody()) {
            byte[] bytes = entrada.readNBytes(TAMANIO_MAXIMO_CUERPO + 1);
            if (bytes.length > TAMANIO_MAXIMO_CUERPO) {
                throw new ApiException(413, "El cuerpo de la petición supera " + TAMANIO_MAXIMO_CUERPO + " bytes");
            }
            return new String(bytes, StandardCharsets.UTF_8);
        }
    }

    private static String normalizar(String ruta) {
        if (ruta == null || ruta.isEmpty()) {
            return "/";
        }
        String resultado = ruta;
        while (resultado.length() > 1 && resultado.endsWith("/")) {
            resultado = resultado.substring(0, resultado.length() - 1);
        }
        return resultado;
    }
}
