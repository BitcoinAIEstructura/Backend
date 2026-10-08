package com.bitcoinai.backend.indicadores;

import java.util.Locale;
import java.util.Map;

/**
 * Crea indicadores por nombre a partir de parámetros en texto (por ejemplo, los
 * de una URL), validándolos.
 *
 * <table>
 *   <caption>Indicadores y parámetros</caption>
 *   <tr><th>Nombre</th><th>Parámetros (por defecto)</th></tr>
 *   <tr><td>sma</td><td>periodo (20)</td></tr>
 *   <tr><td>ema</td><td>periodo (20)</td></tr>
 *   <tr><td>rsi</td><td>periodo (14)</td></tr>
 *   <tr><td>macd</td><td>rapido (12), lento (26), senal (9)</td></tr>
 *   <tr><td>bollinger</td><td>periodo (20), desviaciones (2)</td></tr>
 *   <tr><td>volatilidad</td><td>periodo (20)</td></tr>
 * </table>
 * Todos los periodos deben estar entre 2 y {@value #PERIODO_MAXIMO}. Un periodo
 * mayor que la cantidad de velas no es un error: el indicador devuelve una lista vacía.
 */
public final class FabricaIndicadores {

    /** Nombres aceptados, para los mensajes de error. */
    public static final String NOMBRES = "sma, ema, rsi, macd, bollinger, volatilidad";

    /** Periodo máximo aceptado. */
    public static final int PERIODO_MAXIMO = 1000;

    private FabricaIndicadores() {
    }

    /**
     * Crea un indicador con sus parámetros por defecto.
     *
     * @param nombre nombre del indicador
     * @return el indicador
     * @throws IllegalArgumentException si el nombre no existe
     */
    public static Indicador crear(String nombre) {
        return crear(nombre, Map.of());
    }

    /**
     * Crea un indicador. Los parámetros que no use se ignoran.
     *
     * @param nombre     nombre del indicador (no distingue mayúsculas)
     * @param parametros parámetros en texto; los que falten toman su valor por defecto
     * @return el indicador
     * @throws IllegalArgumentException con un mensaje claro si el nombre o algún parámetro es inválido
     */
    public static Indicador crear(String nombre, Map<String, String> parametros) {
        String clave = nombre == null ? "" : nombre.trim().toLowerCase(Locale.ROOT);
        return switch (clave) {
            case "sma" -> new Sma(periodo(parametros, "periodo", 20));
            case "ema" -> new Ema(periodo(parametros, "periodo", 20));
            case "rsi" -> new Rsi(periodo(parametros, "periodo", 14));
            case "macd" -> {
                int rapido = periodo(parametros, "rapido", 12);
                int lento = periodo(parametros, "lento", 26);
                int senal = periodo(parametros, "senal", 9);
                if (lento <= rapido) {
                    throw new IllegalArgumentException(
                            "Parámetro 'lento' (" + lento + ") debe ser mayor que 'rapido' (" + rapido + ")");
                }
                yield new Macd(rapido, lento, senal);
            }
            case "bollinger" -> new BandasBollinger(periodo(parametros, "periodo", 20),
                    desviaciones(parametros));
            case "volatilidad" -> new Volatilidad(periodo(parametros, "periodo", 20));
            case "" -> throw new IllegalArgumentException(
                    "Falta el parámetro 'indicador'. Valores permitidos: " + NOMBRES);
            default -> throw new IllegalArgumentException(
                    "Indicador desconocido: '" + nombre + "'. Valores permitidos: " + NOMBRES);
        };
    }

    private static int periodo(Map<String, String> parametros, String nombre, int porDefecto) {
        String texto = parametros.get(nombre);
        if (texto == null || texto.isBlank()) {
            return porDefecto;
        }
        try {
            int valor = Integer.parseInt(texto.trim());
            if (valor >= 2 && valor <= PERIODO_MAXIMO) {
                return valor;
            }
        } catch (NumberFormatException e) {
            // cae al error de abajo
        }
        throw new IllegalArgumentException("Parámetro '" + nombre + "' inválido: '" + texto
                + "'. Debe ser un número entero entre 2 y " + PERIODO_MAXIMO);
    }

    private static double desviaciones(Map<String, String> parametros) {
        String texto = parametros.get("desviaciones");
        if (texto == null || texto.isBlank()) {
            return 2.0;
        }
        try {
            double valor = Double.parseDouble(texto.trim());
            if (valor > 0 && valor <= 10) {
                return valor;
            }
        } catch (NumberFormatException e) {
            // cae al error de abajo
        }
        throw new IllegalArgumentException("Parámetro 'desviaciones' inválido: '" + texto
                + "'. Debe ser un número mayor que 0 y como máximo 10");
    }
}
