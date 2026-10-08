package com.bitcoinai.backend.api;

import com.bitcoinai.backend.util.JsonException;
import com.bitcoinai.backend.util.JsonLector;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Datos de una petición que necesita un manejador.
 *
 * @param metodo         método HTTP en mayúsculas, por ejemplo "GET"
 * @param ruta           ruta sin parámetros, por ejemplo "/api/ordenes/7"
 * @param parametros     parámetros de la consulta (?a=1&amp;b=2), ya decodificados
 * @param parametrosRuta parámetros de la ruta, por ejemplo {id=7} para "/api/ordenes/{id}"
 * @param cuerpo         cuerpo de la petición en texto ("" si no tiene)
 */
public record Peticion(
        String metodo,
        String ruta,
        Map<String, String> parametros,
        Map<String, String> parametrosRuta,
        String cuerpo) {

    /**
     * Petición sin parámetros de ruta ni cuerpo.
     *
     * @param metodo     método HTTP
     * @param ruta       ruta
     * @param parametros parámetros de la consulta
     */
    public Peticion(String metodo, String ruta, Map<String, String> parametros) {
        this(metodo, ruta, parametros, Map.of(), "");
    }

    /**
     * Devuelve un parámetro de la consulta o un valor por defecto.
     *
     * @param nombre     nombre del parámetro
     * @param porDefecto valor si no viene o viene vacío
     * @return el valor del parámetro
     */
    public String parametro(String nombre, String porDefecto) {
        String valor = parametros.get(nombre);
        return (valor == null || valor.isEmpty()) ? porDefecto : valor;
    }

    /**
     * Devuelve un parámetro de la ruta.
     *
     * @param nombre nombre entre llaves en el patrón, por ejemplo "id"
     * @return su valor, o null si el patrón no lo tiene
     */
    public String parametroRuta(String nombre) {
        return parametrosRuta.get(nombre);
    }

    /**
     * Lee el cuerpo como un objeto JSON.
     *
     * @return el objeto
     * @throws ApiException 400 si falta el cuerpo, no es JSON válido o no es un objeto
     */
    public Map<String, Object> cuerpoJson() {
        if (cuerpo == null || cuerpo.isBlank()) {
            throw new ApiException(400, "Falta el cuerpo JSON de la petición");
        }
        return objetoJson();
    }

    /**
     * Lee el cuerpo como un objeto JSON, o devuelve un objeto vacío si no hay cuerpo.
     *
     * @return el objeto (vacío si no había cuerpo)
     * @throws ApiException 400 si el cuerpo no es JSON válido o no es un objeto
     */
    public Map<String, Object> cuerpoJsonOpcional() {
        if (cuerpo == null || cuerpo.isBlank()) {
            return Map.of();
        }
        return objetoJson();
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> objetoJson() {
        Object valor;
        try {
            valor = JsonLector.leer(cuerpo);
        } catch (JsonException e) {
            throw new ApiException(400, "Cuerpo JSON inválido: " + e.getMessage());
        }
        if (!(valor instanceof Map)) {
            throw new ApiException(400, "El cuerpo debe ser un objeto JSON, por ejemplo {\"tipo\":\"COMPRA\",\"monto\":500}");
        }
        return (Map<String, Object>) valor;
    }

    /**
     * Convierte una consulta cruda ("a=1&amp;b=x%20y") en un mapa. Si un parámetro
     * se repite, gana el último.
     *
     * @param consulta texto después del "?", o null
     * @return mapa de solo lectura con los parámetros decodificados
     */
    public static Map<String, String> leerConsulta(String consulta) {
        Map<String, String> parametros = new LinkedHashMap<>();
        if (consulta != null && !consulta.isEmpty()) {
            for (String par : consulta.split("&")) {
                if (par.isEmpty()) {
                    continue;
                }
                int igual = par.indexOf('=');
                String nombre = igual < 0 ? par : par.substring(0, igual);
                String valor = igual < 0 ? "" : par.substring(igual + 1);
                parametros.put(decodificar(nombre), decodificar(valor));
            }
        }
        return Collections.unmodifiableMap(parametros);
    }

    private static String decodificar(String texto) {
        try {
            return URLDecoder.decode(texto, StandardCharsets.UTF_8);
        } catch (IllegalArgumentException e) {
            throw new ApiException(400, "Parámetro mal codificado en la URL: " + texto);
        }
    }
}
