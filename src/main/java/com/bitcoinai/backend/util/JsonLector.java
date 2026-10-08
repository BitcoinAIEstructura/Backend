package com.bitcoinai.backend.util;

import com.bitcoinai.backend.estructuras.Lista;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Lector de JSON escrito a mano (analizador descendente recursivo).
 *
 * <p>Convierte el texto en un árbol de objetos Java:
 * <ul>
 *   <li>objeto → {@code Map<String, Object>} (conserva el orden de las claves)</li>
 *   <li>arreglo → {@code Lista<Object>} del proyecto</li>
 *   <li>texto → {@code String}</li>
 *   <li>número → {@code Double}</li>
 *   <li>true / false → {@code Boolean}</li>
 *   <li>null → {@code null}</li>
 * </ul>
 * Lee el texto una sola vez de izquierda a derecha: O(n) en tiempo, con n la
 * longitud del texto.
 */
public final class JsonLector {

    /** Límite de anidamiento para no desbordar la pila con entradas maliciosas. */
    private static final int PROFUNDIDAD_MAXIMA = 512;

    private final String texto;
    private int pos;
    private int profundidad;

    private JsonLector(String texto) {
        this.texto = texto;
    }

    /**
     * Convierte un texto JSON en un árbol de objetos.
     *
     * @param texto el JSON a leer
     * @return el valor leído (Map, Lista, String, Double, Boolean o null)
     * @throws JsonException si el texto no es JSON válido, con la posición del error
     */
    public static Object leer(String texto) {
        if (texto == null) {
            throw new JsonException("El texto JSON es nulo", 0);
        }
        JsonLector lector = new JsonLector(texto);
        lector.saltarEspacios();
        Object valor = lector.leerValor();
        lector.saltarEspacios();
        if (!lector.alFinal()) {
            throw lector.error("Contenido extra después del valor JSON");
        }
        return valor;
    }

    private Object leerValor() {
        if (alFinal()) {
            throw error("Se esperaba un valor y terminó el texto");
        }
        char c = texto.charAt(pos);
        return switch (c) {
            case '{' -> leerObjeto();
            case '[' -> leerArreglo();
            case '"' -> leerTexto();
            case 't' -> leerLiteral("true", Boolean.TRUE);
            case 'f' -> leerLiteral("false", Boolean.FALSE);
            case 'n' -> leerLiteral("null", null);
            default -> {
                if (c == '-' || esDigito(c)) {
                    yield leerNumero();
                }
                throw error("Carácter inesperado '" + c + "'");
            }
        };
    }

    private Map<String, Object> leerObjeto() {
        entrar();
        pos++; // '{'
        Map<String, Object> objeto = new LinkedHashMap<>();
        saltarEspacios();
        if (consumir('}')) {
            profundidad--;
            return objeto;
        }
        while (true) {
            saltarEspacios();
            if (alFinal() || texto.charAt(pos) != '"') {
                throw error("Se esperaba una clave entre comillas");
            }
            String clave = leerTexto();
            saltarEspacios();
            if (!consumir(':')) {
                throw error("Se esperaba ':' después de la clave");
            }
            saltarEspacios();
            objeto.put(clave, leerValor());
            saltarEspacios();
            if (consumir(',')) {
                continue;
            }
            if (consumir('}')) {
                break;
            }
            throw error("Se esperaba ',' o '}' en el objeto");
        }
        profundidad--;
        return objeto;
    }

    private Lista<Object> leerArreglo() {
        entrar();
        pos++; // '['
        Lista<Object> arreglo = new Lista<>();
        saltarEspacios();
        if (consumir(']')) {
            profundidad--;
            return arreglo;
        }
        while (true) {
            saltarEspacios();
            arreglo.agregar(leerValor());
            saltarEspacios();
            if (consumir(',')) {
                continue;
            }
            if (consumir(']')) {
                break;
            }
            throw error("Se esperaba ',' o ']' en el arreglo");
        }
        profundidad--;
        return arreglo;
    }

    private String leerTexto() {
        pos++; // comilla inicial
        StringBuilder sb = new StringBuilder();
        while (true) {
            if (alFinal()) {
                throw error("Texto sin cerrar");
            }
            char c = texto.charAt(pos++);
            if (c == '"') {
                return sb.toString();
            }
            if (c == '\\') {
                if (alFinal()) {
                    throw error("Escape incompleto");
                }
                char escape = texto.charAt(pos++);
                switch (escape) {
                    case '"' -> sb.append('"');
                    case '\\' -> sb.append('\\');
                    case '/' -> sb.append('/');
                    case 'b' -> sb.append('\b');
                    case 'f' -> sb.append('\f');
                    case 'n' -> sb.append('\n');
                    case 'r' -> sb.append('\r');
                    case 't' -> sb.append('\t');
                    case 'u' -> sb.append(leerUnicode());
                    default -> {
                        pos--;
                        throw error("Escape inválido '\\" + escape + "'");
                    }
                }
            } else if (c < 0x20) {
                pos--;
                throw error("Carácter de control sin escapar dentro de un texto");
            } else {
                sb.append(c);
            }
        }
    }

    /** Lee los 4 dígitos hexadecimales de un escape \\uXXXX. Los pares sustitutos se unen solos al agregarse seguidos. */
    private char leerUnicode() {
        if (pos + 4 > texto.length()) {
            throw error("Escape \\u incompleto");
        }
        int valor = 0;
        for (int i = 0; i < 4; i++) {
            int digito = Character.digit(texto.charAt(pos), 16);
            if (digito < 0) {
                throw error("Dígito hexadecimal inválido en escape \\u");
            }
            valor = valor * 16 + digito;
            pos++;
        }
        return (char) valor;
    }

    /** Sigue la gramática de JSON: -? (0 | [1-9][0-9]*) (. [0-9]+)? ([eE] [+-]? [0-9]+)? */
    private Double leerNumero() {
        int inicio = pos;
        if (texto.charAt(pos) == '-') {
            pos++;
        }
        if (alFinal()) {
            throw error("Número incompleto");
        }
        char c = texto.charAt(pos);
        if (c == '0') {
            pos++;
            if (!alFinal() && esDigito(texto.charAt(pos))) {
                throw error("No se permiten ceros a la izquierda");
            }
        } else if (esDigito(c)) {
            leerDigitos();
        } else {
            throw error("Se esperaba un dígito");
        }
        if (!alFinal() && texto.charAt(pos) == '.') {
            pos++;
            if (!leerDigitos()) {
                throw error("Se esperaba un dígito después del punto decimal");
            }
        }
        if (!alFinal() && (texto.charAt(pos) == 'e' || texto.charAt(pos) == 'E')) {
            pos++;
            if (!alFinal() && (texto.charAt(pos) == '+' || texto.charAt(pos) == '-')) {
                pos++;
            }
            if (!leerDigitos()) {
                throw error("Se esperaba un dígito en el exponente");
            }
        }
        return Double.parseDouble(texto.substring(inicio, pos));
    }

    private boolean leerDigitos() {
        int inicio = pos;
        while (!alFinal() && esDigito(texto.charAt(pos))) {
            pos++;
        }
        return pos > inicio;
    }

    private Object leerLiteral(String literal, Object valor) {
        if (!texto.startsWith(literal, pos)) {
            throw error("Literal inválido, se esperaba '" + literal + "'");
        }
        pos += literal.length();
        return valor;
    }

    private void entrar() {
        if (++profundidad > PROFUNDIDAD_MAXIMA) {
            throw error("Anidamiento demasiado profundo (máximo " + PROFUNDIDAD_MAXIMA + ")");
        }
    }

    private boolean consumir(char esperado) {
        if (!alFinal() && texto.charAt(pos) == esperado) {
            pos++;
            return true;
        }
        return false;
    }

    private void saltarEspacios() {
        while (!alFinal()) {
            char c = texto.charAt(pos);
            if (c != ' ' && c != '\t' && c != '\n' && c != '\r') {
                return;
            }
            pos++;
        }
    }

    private boolean alFinal() {
        return pos >= texto.length();
    }

    private static boolean esDigito(char c) {
        return c >= '0' && c <= '9';
    }

    private JsonException error(String mensaje) {
        return new JsonException(mensaje, pos);
    }
}
