package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import java.util.Locale;
import java.util.Map;

/**
 * Crea estrategias por nombre a partir de parámetros en texto (por ejemplo, los
 * de una URL), y las combinaciones candidatas para la validación.
 *
 * <table>
 *   <caption>Estrategias y parámetros</caption>
 *   <tr><th>Nombre</th><th>Parámetros (por defecto)</th></tr>
 *   <tr><td>cruce</td><td>corta (20), larga (50)</td></tr>
 *   <tr><td>rsi</td><td>periodo (14), sobreventa (30), sobrecompra (70)</td></tr>
 *   <tr><td>macd</td><td>rapido (12), lento (26), senal (9)</td></tr>
 *   <tr><td>combinada</td><td>pesoCruce, pesoRsi, pesoMacd (1 cada uno) y los de las tres anteriores</td></tr>
 * </table>
 */
public final class FabricaEstrategias {

    /** Nombres aceptados, para los mensajes de error. */
    public static final String NOMBRES = "cruce, rsi, macd, combinada";

    private FabricaEstrategias() {
    }

    /**
     * Crea una estrategia con sus parámetros por defecto.
     *
     * @param nombre nombre de la estrategia
     * @return la estrategia
     * @throws IllegalArgumentException si el nombre no existe
     */
    public static Estrategia crear(String nombre) {
        return crear(nombre, Map.of());
    }

    /**
     * Crea una estrategia. Los parámetros que no use se ignoran.
     *
     * @param nombre     nombre (no distingue mayúsculas)
     * @param parametros parámetros en texto; los que falten toman su valor por defecto
     * @return la estrategia
     * @throws IllegalArgumentException con un mensaje claro si algo es inválido
     */
    public static Estrategia crear(String nombre, Map<String, String> parametros) {
        String clave = nombre == null ? "" : nombre.trim().toLowerCase(Locale.ROOT);
        return switch (clave) {
            case "cruce" -> cruce(parametros);
            case "rsi" -> rsi(parametros);
            case "macd" -> macd(parametros);
            case "combinada" -> {
                Lista<EstrategiaCombinada.Componente> componentes = new Lista<>();
                componentes.agregar(new EstrategiaCombinada.Componente(cruce(parametros), peso(parametros, "pesoCruce")));
                componentes.agregar(new EstrategiaCombinada.Componente(rsi(parametros), peso(parametros, "pesoRsi")));
                componentes.agregar(new EstrategiaCombinada.Componente(macd(parametros), peso(parametros, "pesoMacd")));
                try {
                    yield new EstrategiaCombinada(componentes);
                } catch (IllegalArgumentException e) {
                    throw new IllegalArgumentException("Al menos uno de pesoCruce, pesoRsi o pesoMacd debe ser mayor que 0");
                }
            }
            case "" -> throw new IllegalArgumentException("Falta el parámetro 'estrategia'. Valores permitidos: " + NOMBRES);
            default -> throw new IllegalArgumentException(
                    "Estrategia desconocida: '" + nombre + "'. Valores permitidos: " + NOMBRES);
        };
    }

    /**
     * Combinaciones de parámetros que prueba la validación entrenamiento/prueba.
     *
     * @param nombre nombre de la estrategia
     * @return la estrategia con distintos parámetros
     * @throws IllegalArgumentException si el nombre no existe
     */
    public static Lista<Estrategia> candidatos(String nombre) {
        String clave = nombre == null ? "" : nombre.trim().toLowerCase(Locale.ROOT);
        Lista<Estrategia> lista = new Lista<>();
        switch (clave) {
            case "cruce" -> {
                for (int corta : new int[] {5, 10, 20}) {
                    for (int larga : new int[] {30, 50, 100}) {
                        lista.agregar(new CruceDeMedias(corta, larga));
                    }
                }
            }
            case "rsi" -> {
                for (int periodo : new int[] {7, 14, 21}) {
                    for (int nivel : new int[] {30, 25, 20}) {
                        lista.agregar(new EstrategiaRsi(periodo, nivel, 100 - nivel));
                    }
                }
            }
            case "macd" -> {
                lista.agregar(new EstrategiaMacd(12, 26, 9));
                lista.agregar(new EstrategiaMacd(8, 17, 9));
                lista.agregar(new EstrategiaMacd(5, 35, 5));
            }
            case "combinada" -> {
                lista.agregar(new EstrategiaCombinada(1, 1, 1));
                lista.agregar(new EstrategiaCombinada(2, 1, 1));
                lista.agregar(new EstrategiaCombinada(1, 2, 1));
                lista.agregar(new EstrategiaCombinada(1, 1, 2));
            }
            default -> throw new IllegalArgumentException(
                    "Estrategia desconocida: '" + nombre + "'. Valores permitidos: " + NOMBRES);
        }
        return lista;
    }

    private static CruceDeMedias cruce(Map<String, String> parametros) {
        int corta = entero(parametros, "corta", 20, 2, 500);
        int larga = entero(parametros, "larga", 50, 3, 1000);
        if (larga <= corta) {
            throw new IllegalArgumentException(
                    "Parámetro 'larga' (" + larga + ") debe ser mayor que 'corta' (" + corta + ")");
        }
        return new CruceDeMedias(corta, larga);
    }

    private static EstrategiaRsi rsi(Map<String, String> parametros) {
        return new EstrategiaRsi(entero(parametros, "periodo", 14, 2, 500),
                entero(parametros, "sobreventa", 30, 1, 49),
                entero(parametros, "sobrecompra", 70, 51, 99));
    }

    private static EstrategiaMacd macd(Map<String, String> parametros) {
        int rapido = entero(parametros, "rapido", 12, 2, 500);
        int lento = entero(parametros, "lento", 26, 3, 1000);
        int senal = entero(parametros, "senal", 9, 2, 500);
        if (lento <= rapido) {
            throw new IllegalArgumentException(
                    "Parámetro 'lento' (" + lento + ") debe ser mayor que 'rapido' (" + rapido + ")");
        }
        return new EstrategiaMacd(rapido, lento, senal);
    }

    private static int entero(Map<String, String> parametros, String nombre, int porDefecto, int minimo, int maximo) {
        String texto = parametros.get(nombre);
        if (texto == null || texto.isBlank()) {
            return porDefecto;
        }
        try {
            int valor = Integer.parseInt(texto.trim());
            if (valor >= minimo && valor <= maximo) {
                return valor;
            }
        } catch (NumberFormatException e) {
            // cae al error de abajo
        }
        throw new IllegalArgumentException("Parámetro '" + nombre + "' inválido: '" + texto
                + "'. Debe ser un número entero entre " + minimo + " y " + maximo);
    }

    private static double peso(Map<String, String> parametros, String nombre) {
        String texto = parametros.get(nombre);
        if (texto == null || texto.isBlank()) {
            return 1.0;
        }
        try {
            double valor = Double.parseDouble(texto.trim());
            if (valor >= 0 && valor <= 10) {
                return valor;
            }
        } catch (NumberFormatException e) {
            // cae al error de abajo
        }
        throw new IllegalArgumentException("Parámetro '" + nombre + "' inválido: '" + texto
                + "'. Debe ser un número entre 0 y 10");
    }
}
