package com.bitcoinai.backend.mercado;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import com.bitcoinai.backend.util.JsonException;
import com.bitcoinai.backend.util.JsonLector;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.logging.Logger;
import java.util.regex.Pattern;

/**
 * Fuente de mercado que consulta la API pública de Binance (no necesita clave).
 *
 * <ul>
 *   <li>{@code GET /api/v3/klines}: velas; cada una llega como un arreglo
 *       {@code [tiempoApertura, "apertura", "maximo", "minimo", "cierre", "volumen", tiempoCierre, ...]}.</li>
 *   <li>{@code GET /api/v3/ticker/price}: último precio, {@code {"symbol":"BTCUSDT","price":"67000.00"}}.</li>
 * </ul>
 * La URL base se toma de la variable de entorno {@code BINANCE_BASE_URL}
 * (por defecto {@value #URL_BASE_POR_DEFECTO}), porque en algunos países hay que cambiarla.
 */
public class ClienteBinance implements FuenteDeMercado {

    /** URL base por defecto de la API de Binance. */
    public static final String URL_BASE_POR_DEFECTO = "https://api.binance.com";

    /** Máximo de velas que Binance entrega en una sola petición. */
    public static final int LIMITE_POR_PETICION = 1000;

    /** Mensaje cuando Binance responde 451 porque la región del servidor está restringida. */
    public static final String MENSAJE_REGION_RESTRINGIDA =
            "Binance no está disponible desde esta región; cambia la región del servicio o la URL base";

    private static final int HTTP_REGION_RESTRINGIDA = 451;
    private static final Logger LOG = Logger.getLogger(ClienteBinance.class.getName());

    private static final Duration TIEMPO_CONEXION = Duration.ofSeconds(5);
    private static final Duration TIEMPO_RESPUESTA = Duration.ofSeconds(10);
    private static final Duration PAUSA_REINTENTO = Duration.ofMillis(500);
    private static final int REINTENTOS = 1;
    private static final Pattern SIMBOLO_VALIDO = Pattern.compile("[A-Z0-9]{2,20}");

    private final String urlBase;
    private final HttpClient http;
    private final Duration tiempoRespuesta;
    private final int reintentos;
    private final Duration pausaReintento;

    /** Crea el cliente con la URL de {@code BINANCE_BASE_URL} o la de por defecto. */
    public ClienteBinance() {
        this(resolverUrlBase(System.getenv("BINANCE_BASE_URL")));
    }

    /**
     * Crea el cliente con una URL base dada y los tiempos de espera por defecto
     * (5 s de conexión, 10 s de respuesta, un reintento).
     *
     * @param urlBase URL base, por ejemplo "https://api.binance.com"
     */
    public ClienteBinance(String urlBase) {
        this(urlBase,
                HttpClient.newBuilder().connectTimeout(TIEMPO_CONEXION).build(),
                TIEMPO_RESPUESTA, REINTENTOS, PAUSA_REINTENTO);
    }

    /**
     * Crea el cliente con todos los parámetros (útil en pruebas).
     *
     * @param urlBase         URL base sin barra final
     * @param http            cliente HTTP, que ya trae su tiempo de conexión
     * @param tiempoRespuesta tiempo máximo de espera de cada respuesta
     * @param reintentos      reintentos ante fallos de red o errores 5xx
     * @param pausaReintento  espera antes de cada reintento
     */
    public ClienteBinance(String urlBase, HttpClient http, Duration tiempoRespuesta,
                          int reintentos, Duration pausaReintento) {
        this.urlBase = resolverUrlBase(urlBase);
        this.http = Objects.requireNonNull(http, "http");
        this.tiempoRespuesta = Objects.requireNonNull(tiempoRespuesta, "tiempoRespuesta");
        if (reintentos < 0) {
            throw new IllegalArgumentException("reintentos no puede ser negativo");
        }
        this.reintentos = reintentos;
        this.pausaReintento = Objects.requireNonNull(pausaReintento, "pausaReintento");
    }

    /**
     * Devuelve la URL base que usa este cliente.
     *
     * @return la URL base sin barra final
     */
    public String getUrlBase() {
        return urlBase;
    }

    /**
     * {@inheritDoc}
     *
     * <p>Si se piden más de {@value #LIMITE_POR_PETICION} velas, hace varias
     * peticiones hacia atrás en el tiempo usando {@code endTime}: cada lote se
     * recorre con el iterador hacia atrás de la ListaDoble y se agrega al inicio
     * del resultado, descartando las velas que ya estaban (duplicadas).
     * Complejidad: O(cantidad) en memoria y procesamiento, más
     * ⌈cantidad / 1000⌉ peticiones HTTP.
     */
    @Override
    public ListaDoble<Vela> obtenerVelas(String simbolo, Intervalo intervalo, int cantidad) {
        String simboloNormalizado = normalizarSimbolo(simbolo);
        Objects.requireNonNull(intervalo, "intervalo");
        if (cantidad < 1) {
            throw new IllegalArgumentException("La cantidad de velas debe ser al menos 1");
        }

        ListaDoble<Vela> resultado = new ListaDoble<>();
        Long tiempoFinal = null;
        while (resultado.tamanio() < cantidad) {
            // Al paginar se pide una vela extra por si la fuente repite la del borde.
            int faltan = cantidad - resultado.tamanio() + (tiempoFinal == null ? 0 : 1);
            int limite = Math.min(faltan, LIMITE_POR_PETICION);
            ListaDoble<Vela> lote = pedirKlines(simboloNormalizado, intervalo, limite, tiempoFinal);
            ValidadorVelas.validar(lote);

            // El lote va de la más antigua a la más reciente; lo recorremos al revés
            // para ir agregando al inicio y solo aceptamos velas más antiguas que la
            // primera que ya tenemos, así no entran duplicados.
            long limiteSuperior = resultado.estaVacia() ? Long.MAX_VALUE : resultado.primero().tiempoApertura();
            int agregadas = 0;
            Iterator<Vela> haciaAtras = lote.iteradorAtras();
            while (haciaAtras.hasNext() && resultado.tamanio() < cantidad) {
                Vela vela = haciaAtras.next();
                if (vela.tiempoApertura() < limiteSuperior) {
                    resultado.agregarInicio(vela);
                    limiteSuperior = vela.tiempoApertura();
                    agregadas++;
                }
            }
            if (agregadas == 0 || lote.tamanio() < limite) {
                break; // no hay más historial
            }
            tiempoFinal = resultado.primero().tiempoApertura() - 1;
        }
        ValidadorVelas.validar(resultado);
        return resultado;
    }

    /** {@inheritDoc} */
    @Override
    public double obtenerPrecioActual(String simbolo) {
        String cuerpo = pedir("/api/v3/ticker/price?symbol=" + normalizarSimbolo(simbolo));
        Object raiz = leerJson(cuerpo, "precio");
        if (!(raiz instanceof Map<?, ?> objeto) || !objeto.containsKey("price")) {
            throw new MercadoException("Respuesta de precio inválida: falta el campo 'price'");
        }
        double precio = comoDouble(objeto.get("price"), "price");
        if (!(precio > 0) || Double.isInfinite(precio)) {
            throw new MercadoException("Respuesta de precio inválida: el precio debe ser positivo");
        }
        return precio;
    }

    private ListaDoble<Vela> pedirKlines(String simbolo, Intervalo intervalo, int limite, Long tiempoFinal) {
        StringBuilder ruta = new StringBuilder("/api/v3/klines?symbol=").append(simbolo)
                .append("&interval=").append(intervalo.codigo())
                .append("&limit=").append(limite);
        if (tiempoFinal != null) {
            ruta.append("&endTime=").append(tiempoFinal);
        }
        return convertirKlines(pedir(ruta.toString()));
    }

    /**
     * Convierte el texto de una respuesta de {@code /api/v3/klines} en velas,
     * en el mismo orden en que llegan. No valida la coherencia de las velas.
     * Complejidad: O(n) en la longitud del texto.
     *
     * @param json cuerpo de la respuesta
     * @return las velas leídas
     * @throws MercadoException si el formato no es el esperado
     */
    static ListaDoble<Vela> convertirKlines(String json) {
        Object raiz = leerJson(json, "klines");
        if (!(raiz instanceof Lista<?> filas)) {
            throw new MercadoException("Respuesta de klines inválida: se esperaba un arreglo");
        }
        ListaDoble<Vela> velas = new ListaDoble<>();
        int indice = 0;
        for (Object fila : filas) {
            if (!(fila instanceof Lista<?> campos) || campos.tamanio() < 7) {
                throw new MercadoException(
                        "Respuesta de klines inválida: la vela " + indice + " no tiene al menos 7 campos");
            }
            velas.agregarFinal(new Vela(
                    comoLong(campos.obtener(0), "tiempoApertura"),
                    comoDouble(campos.obtener(1), "apertura"),
                    comoDouble(campos.obtener(2), "maximo"),
                    comoDouble(campos.obtener(3), "minimo"),
                    comoDouble(campos.obtener(4), "cierre"),
                    comoDouble(campos.obtener(5), "volumen"),
                    comoLong(campos.obtener(6), "tiempoCierre")));
            indice++;
        }
        return velas;
    }

    /**
     * Hace un GET y devuelve el cuerpo si la respuesta es 200. Reintenta ante
     * fallos de red, tiempo agotado o errores 5xx; los 4xx no se reintentan
     * porque repetir la misma petición no los arregla. Un 451 (región
     * restringida) se registra y da {@link #MENSAJE_REGION_RESTRINGIDA}.
     */
    private String pedir(String rutaYConsulta) {
        HttpRequest peticion = HttpRequest.newBuilder(URI.create(urlBase + rutaYConsulta))
                .timeout(tiempoRespuesta)
                .header("Accept", "application/json")
                .GET()
                .build();
        MercadoException ultimoError = null;
        for (int intento = 0; intento <= reintentos; intento++) {
            if (intento > 0) {
                esperar(pausaReintento);
            }
            try {
                HttpResponse<String> respuesta =
                        http.send(peticion, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
                int codigo = respuesta.statusCode();
                if (codigo == 200) {
                    return respuesta.body();
                }
                if (codigo == HTTP_REGION_RESTRINGIDA) {
                    // Binance bloquea algunas regiones (por ejemplo servidores en EE. UU.). Reintentar no sirve.
                    LOG.warning(MENSAJE_REGION_RESTRINGIDA + " (HTTP 451 desde " + urlBase + ")");
                    throw new MercadoException(MENSAJE_REGION_RESTRINGIDA);
                }
                ultimoError = new MercadoException(mensajeDeError(codigo, respuesta.body()));
                if (codigo < 500) {
                    throw ultimoError;
                }
            } catch (HttpTimeoutException e) {
                ultimoError = new MercadoException("Binance no respondió a tiempo", e);
            } catch (IOException e) {
                ultimoError = new MercadoException("No se pudo conectar con Binance: " + e.getMessage(), e);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new MercadoException("La petición a Binance fue interrumpida", e);
            }
        }
        throw ultimoError;
    }

    /** Arma un mensaje claro e incluye el campo "msg" que Binance manda en sus errores, si viene. */
    private static String mensajeDeError(int codigo, String cuerpo) {
        String mensaje = "Binance respondió HTTP " + codigo;
        try {
            if (JsonLector.leer(cuerpo) instanceof Map<?, ?> objeto && objeto.get("msg") instanceof String msg) {
                return mensaje + ": " + msg;
            }
        } catch (JsonException e) {
            // el cuerpo no es JSON; basta con el código
        }
        return mensaje;
    }

    private static void esperar(Duration pausa) {
        if (pausa.isZero()) {
            return;
        }
        try {
            Thread.sleep(pausa.toMillis());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new MercadoException("La petición a Binance fue interrumpida", e);
        }
    }

    private static Object leerJson(String json, String que) {
        try {
            return JsonLector.leer(json);
        } catch (JsonException e) {
            throw new MercadoException("Respuesta de " + que + " no es JSON válido: " + e.getMessage(), e);
        }
    }

    private static double comoDouble(Object valor, String campo) {
        if (valor instanceof Number numero) {
            return numero.doubleValue();
        }
        if (valor instanceof String texto) {
            try {
                return Double.parseDouble(texto);
            } catch (NumberFormatException e) {
                // cae al error de abajo
            }
        }
        throw new MercadoException("Campo '" + campo + "' inválido en la respuesta de Binance: " + valor);
    }

    private static long comoLong(Object valor, String campo) {
        if (valor instanceof Number numero) {
            return numero.longValue();
        }
        if (valor instanceof String texto) {
            try {
                return Long.parseLong(texto);
            } catch (NumberFormatException e) {
                // cae al error de abajo
            }
        }
        throw new MercadoException("Campo '" + campo + "' inválido en la respuesta de Binance: " + valor);
    }

    /** Pasa a mayúsculas y exige solo letras y dígitos, para no inyectar nada en la URL. */
    private static String normalizarSimbolo(String simbolo) {
        String normalizado = simbolo == null ? "" : simbolo.trim().toUpperCase(Locale.ROOT);
        if (!SIMBOLO_VALIDO.matcher(normalizado).matches()) {
            throw new IllegalArgumentException("Símbolo inválido: " + simbolo);
        }
        return normalizado;
    }

    /**
     * Decide la URL base: la dada si no está vacía, o la de por defecto; sin barra final.
     *
     * @param valor valor configurado (puede ser null)
     * @return la URL base a usar
     */
    static String resolverUrlBase(String valor) {
        String url = (valor == null || valor.isBlank()) ? URL_BASE_POR_DEFECTO : valor.trim();
        while (url.endsWith("/")) {
            url = url.substring(0, url.length() - 1);
        }
        return url;
    }
}
