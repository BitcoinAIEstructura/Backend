package com.bitcoinai.backend.api;

import static com.bitcoinai.backend.api.ClienteHttpPrueba.get;
import static com.bitcoinai.backend.api.ClienteHttpPrueba.json;
import static com.bitcoinai.backend.api.ClienteHttpPrueba.pedir;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.net.http.HttpResponse;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class RouterTest {

    private Servidor servidor;
    private int puerto;

    @BeforeEach
    void iniciar() throws IOException {
        Router router = new Router()
                .get("/eco", p -> {
                    Map<String, Object> cuerpo = new LinkedHashMap<>();
                    cuerpo.put("metodo", p.metodo());
                    cuerpo.put("ruta", p.ruta());
                    cuerpo.put("parametros", p.parametros());
                    return Respuesta.ok(cuerpo);
                })
                .agregar("post", "/eco", p -> new Respuesta(201, Map.of("creado", true)))
                .get("/conflicto", p -> {
                    throw new ApiException(409, "Ya existe");
                })
                .get("/cosas/{id}", p -> Respuesta.ok(Map.of("id", p.parametroRuta("id"))))
                .delete("/cosas/{id}", p -> Respuesta.ok(Map.of("borrado", p.parametroRuta("id"))))
                .post("/cosas/especial", p -> Respuesta.ok(Map.of("especial", true)))
                .get("/cosas/{id}/partes/{parte}", p -> Respuesta.ok(p.parametrosRuta()))
                .post("/eco-cuerpo", p -> Respuesta.ok(p.cuerpoJson()));
        servidor = new Servidor("127.0.0.1", 0, router, "*");
        servidor.iniciar();
        puerto = servidor.puerto();
    }

    @AfterEach
    void detener() {
        servidor.detener(0);
    }

    @Test
    void entregaMetodoRutaYParametrosDecodificados() {
        Map<String, Object> cuerpo = json(get(puerto, "/eco/?nombre=Juan%20P%C3%A9rez&x=1&x=2&vacio"));
        assertEquals("GET", cuerpo.get("metodo"));
        assertEquals("/eco", cuerpo.get("ruta"));
        assertEquals("{nombre=Juan Pérez, x=2, vacio=}", cuerpo.get("parametros").toString());
    }

    @Test
    void mismoCaminoConVariosMetodos() {
        HttpResponse<String> r = pedir(puerto, "POST", "/eco");
        assertEquals(201, r.statusCode());
        assertEquals("{\"creado\":true}", r.body());
        HttpResponse<String> noPermitido = pedir(puerto, "PUT", "/eco");
        assertEquals(405, noPermitido.statusCode());
        assertEquals("GET, POST", noPermitido.headers().firstValue("Allow").orElse(""));
    }

    @Test
    void apiExceptionSeConvierteEnSuCodigo() {
        HttpResponse<String> r = get(puerto, "/conflicto");
        assertEquals(409, r.statusCode());
        assertEquals("{\"error\":\"Ya existe\"}", r.body());
    }

    @Test
    void parametrosDeRuta() {
        assertEquals("{\"id\":\"42\"}", get(puerto, "/cosas/42").body());
        assertEquals("{\"borrado\":\"7\"}", pedir(puerto, "DELETE", "/cosas/7/").body());
        assertEquals("{\"id\":\"3\",\"parte\":\"rueda\"}", get(puerto, "/cosas/3/partes/rueda").body());
        assertEquals(404, get(puerto, "/cosas/3/partes").statusCode());
        assertEquals(404, get(puerto, "/cosas/1/2").statusCode());
    }

    @Test
    void laRutaExactaTienePrioridadSobreLaDeParametros() {
        assertEquals("{\"especial\":true}", pedir(puerto, "POST", "/cosas/especial").body());
        // GET /cosas/especial: la ruta exacta existe solo con POST → 405, no se toma como id
        HttpResponse<String> r = get(puerto, "/cosas/especial");
        assertEquals(405, r.statusCode());
        assertEquals("POST", r.headers().firstValue("Allow").orElse(""));
        HttpResponse<String> metodo = pedir(puerto, "POST", "/cosas/9");
        assertEquals(405, metodo.statusCode());
        assertEquals("GET, DELETE", metodo.headers().firstValue("Allow").orElse(""));
    }

    @Test
    void elCuerpoLlegaAlManejador() {
        HttpResponse<String> r = ClienteHttpPrueba.enviar(puerto, "POST", "/eco-cuerpo", "{\"a\":1,\"b\":\"ñ\"}");
        assertEquals("{\"a\":1,\"b\":\"ñ\"}", r.body());
        String grande = "{\"x\":\"" + "a".repeat(Router.TAMANIO_MAXIMO_CUERPO) + "\"}";
        assertEquals(413, ClienteHttpPrueba.enviar(puerto, "POST", "/eco-cuerpo", grande).statusCode());
    }

    @Test
    void rutaDuplicadaSeRechazaAlRegistrar() {
        Router router = new Router().get("/a", p -> Respuesta.ok(Map.of()));
        assertThrows(IllegalArgumentException.class, () -> router.get("/a/", p -> Respuesta.ok(Map.of())));
    }

    @Test
    void leerConsultaSinTexto() {
        assertEquals(0, Peticion.leerConsulta(null).size());
        assertEquals(0, Peticion.leerConsulta("").size());
        assertEquals("b", new Peticion("GET", "/", Peticion.leerConsulta("a=b")).parametro("a", "x"));
        assertEquals("x", new Peticion("GET", "/", Peticion.leerConsulta("a=")).parametro("a", "x"));
    }

    @Test
    void parametroMalCodificadoEsUn400() {
        ApiException e = assertThrows(ApiException.class, () -> Peticion.leerConsulta("cantidad=%ZZ"));
        assertEquals(400, e.getCodigo());
    }
}
