package com.bitcoinai.backend.util;

import java.lang.reflect.Method;
import java.lang.reflect.RecordComponent;
import java.util.Map;

/**
 * Escritor de JSON escrito a mano.
 *
 * <p>Tipos soportados:
 * <ul>
 *   <li>{@code null}, {@code Boolean}, {@code String}, {@code Character}</li>
 *   <li>números: enteros tal cual; {@code Double}/{@code Float} sin ".0" cuando son enteros</li>
 *   <li>{@code Map} → objeto (claves con {@code String.valueOf})</li>
 *   <li>cualquier {@code Iterable}, como {@code Lista} y {@code ListaDoble} → arreglo</li>
 *   <li>records → objeto con un campo por componente, en orden de declaración</li>
 *   <li>enums → su nombre como texto</li>
 * </ul>
 * Recorre cada valor una vez: O(n) en el tamaño del resultado.
 */
public final class JsonEscritor {

    private JsonEscritor() {
    }

    /**
     * Convierte un valor en texto JSON compacto (sin espacios).
     *
     * @param valor valor a convertir
     * @return el texto JSON
     * @throws IllegalArgumentException si hay un tipo no soportado o un número NaN o infinito
     */
    public static String escribir(Object valor) {
        StringBuilder sb = new StringBuilder();
        escribir(valor, sb);
        return sb.toString();
    }

    private static void escribir(Object valor, StringBuilder sb) {
        if (valor == null) {
            sb.append("null");
        } else if (valor instanceof String texto) {
            escribirTexto(texto, sb);
        } else if (valor instanceof Character caracter) {
            escribirTexto(String.valueOf(caracter), sb);
        } else if (valor instanceof Boolean booleano) {
            sb.append(booleano);
        } else if (valor instanceof Double || valor instanceof Float) {
            escribirDecimal(((Number) valor).doubleValue(), sb);
        } else if (valor instanceof Number numero) {
            sb.append(numero);
        } else if (valor instanceof Enum<?> enumeracion) {
            escribirTexto(enumeracion.name(), sb);
        } else if (valor instanceof Map<?, ?> mapa) {
            escribirObjeto(mapa, sb);
        } else if (valor instanceof Iterable<?> iterable) {
            escribirArreglo(iterable, sb);
        } else if (valor instanceof Record registro) {
            escribirRecord(registro, sb);
        } else {
            throw new IllegalArgumentException(
                    "Tipo no soportado por JsonEscritor: " + valor.getClass().getName());
        }
    }

    private static void escribirDecimal(double numero, StringBuilder sb) {
        if (!Double.isFinite(numero)) {
            throw new IllegalArgumentException("JSON no admite NaN ni infinito: " + numero);
        }
        if (numero == Math.rint(numero) && Math.abs(numero) < 1e15) {
            sb.append((long) numero);
        } else {
            sb.append(numero);
        }
    }

    private static void escribirTexto(String texto, StringBuilder sb) {
        sb.append('"');
        for (int i = 0; i < texto.length(); i++) {
            char c = texto.charAt(i);
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\b' -> sb.append("\\b");
                case '\f' -> sb.append("\\f");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
                }
            }
        }
        sb.append('"');
    }

    private static void escribirObjeto(Map<?, ?> mapa, StringBuilder sb) {
        sb.append('{');
        boolean primero = true;
        for (Map.Entry<?, ?> entrada : mapa.entrySet()) {
            if (!primero) {
                sb.append(',');
            }
            primero = false;
            escribirTexto(String.valueOf(entrada.getKey()), sb);
            sb.append(':');
            escribir(entrada.getValue(), sb);
        }
        sb.append('}');
    }

    private static void escribirArreglo(Iterable<?> iterable, StringBuilder sb) {
        sb.append('[');
        boolean primero = true;
        for (Object elemento : iterable) {
            if (!primero) {
                sb.append(',');
            }
            primero = false;
            escribir(elemento, sb);
        }
        sb.append(']');
    }

    private static void escribirRecord(Record registro, StringBuilder sb) {
        sb.append('{');
        boolean primero = true;
        for (RecordComponent componente : registro.getClass().getRecordComponents()) {
            if (!primero) {
                sb.append(',');
            }
            primero = false;
            escribirTexto(componente.getName(), sb);
            sb.append(':');
            escribir(leerComponente(registro, componente), sb);
        }
        sb.append('}');
    }

    private static Object leerComponente(Record registro, RecordComponent componente) {
        try {
            Method accesor = componente.getAccessor();
            accesor.setAccessible(true);
            return accesor.invoke(registro);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(
                    "No se pudo leer el campo " + componente.getName() + " del record", e);
        }
    }
}
