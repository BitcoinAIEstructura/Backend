package com.bitcoinai.backend.api;

import com.bitcoinai.backend.mercado.ClienteBinance;
import java.util.Locale;
import java.util.Objects;
import java.util.function.Function;
import java.util.regex.Pattern;

/**
 * Configuración del backend, leída de variables de entorno con valores por defecto.
 * No contiene secretos: todo lo que usa el backend es público.
 *
 * @param puerto           puerto HTTP ({@code PORT}, por defecto 8080; Railway lo inyecta)
 * @param urlBaseBinance   URL base de Binance ({@code BINANCE_BASE_URL})
 * @param origenPermitido  origen permitido para CORS ({@code ORIGEN_PERMITIDO}, por defecto *)
 * @param ttlCacheSegundos segundos que se guardan en caché los datos de mercado
 *                         ({@code TTL_CACHE_SEGUNDOS}, por defecto 30)
 * @param simbolo          par de mercado ({@code SIMBOLO}, por defecto BTCUSDT)
 * @param maxStreams       conexiones simultáneas a /api/stream ({@code MAX_STREAMS}, por defecto 50)
 * @param dataDir          carpeta donde se guarda la simulación ({@code DATA_DIR}, por defecto ./data)
 */
public record Configuracion(
        int puerto,
        String urlBaseBinance,
        String origenPermitido,
        int ttlCacheSegundos,
        String simbolo,
        int maxStreams,
        String dataDir) {

    private static final Pattern SIMBOLO_VALIDO = Pattern.compile("[A-Z0-9]{2,20}");

    /**
     * Lee la configuración de las variables de entorno del proceso.
     *
     * @return la configuración
     * @throws IllegalArgumentException si alguna variable tiene un valor inválido
     */
    public static Configuracion desdeEntorno() {
        return desde(System::getenv);
    }

    /**
     * Lee la configuración de una fuente de variables (por ejemplo un Map en las pruebas).
     *
     * @param entorno función que devuelve el valor de una variable, o null si no existe
     * @return la configuración
     * @throws IllegalArgumentException si alguna variable tiene un valor inválido
     */
    public static Configuracion desde(Function<String, String> entorno) {
        Objects.requireNonNull(entorno, "entorno");
        int puerto = entero(entorno, "PORT", 8080, 0, 65_535);
        String urlBase = texto(entorno, "BINANCE_BASE_URL", ClienteBinance.URL_BASE_POR_DEFECTO);
        String origen = texto(entorno, "ORIGEN_PERMITIDO", "*");
        int ttl = entero(entorno, "TTL_CACHE_SEGUNDOS", 30, 0, 86_400);
        String simbolo = texto(entorno, "SIMBOLO", "BTCUSDT").toUpperCase(Locale.ROOT);
        if (!SIMBOLO_VALIDO.matcher(simbolo).matches()) {
            throw new IllegalArgumentException("SIMBOLO inválido: " + simbolo);
        }
        int maxStreams = entero(entorno, "MAX_STREAMS", Publicador.MAXIMO_POR_DEFECTO, 1, 10_000);
        String dataDir = texto(entorno, "DATA_DIR", "./data");
        return new Configuracion(puerto, urlBase, origen, ttl, simbolo, maxStreams, dataDir);
    }

    private static String texto(Function<String, String> entorno, String nombre, String porDefecto) {
        String valor = entorno.apply(nombre);
        return (valor == null || valor.isBlank()) ? porDefecto : valor.trim();
    }

    private static int entero(Function<String, String> entorno, String nombre, int porDefecto, int minimo, int maximo) {
        String valor = entorno.apply(nombre);
        if (valor == null || valor.isBlank()) {
            return porDefecto;
        }
        try {
            int numero = Integer.parseInt(valor.trim());
            if (numero >= minimo && numero <= maximo) {
                return numero;
            }
        } catch (NumberFormatException e) {
            // cae al error de abajo
        }
        throw new IllegalArgumentException(
                nombre + " debe ser un número entero entre " + minimo + " y " + maximo + ": " + valor);
    }
}
