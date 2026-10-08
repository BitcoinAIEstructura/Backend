package com.bitcoinai.backend.api;

import static com.bitcoinai.backend.api.ClienteHttpPrueba.get;
import static com.bitcoinai.backend.api.ClienteHttpPrueba.json;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estrategia.Pronostico;
import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.mercado.MercadoException;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.io.IOException;
import java.net.http.HttpResponse;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** Pruebas de /api/senal y /api/backtest con una FuenteFalsa de 500 velas que siempre suben. */
class EstrategiaApiTest {

    private FuenteFalsa fuente;
    private Servidor servidor;
    private int puerto;

    @BeforeEach
    void iniciar() throws IOException {
        fuente = new FuenteFalsa();
        servidor = new Servidor("127.0.0.1", 0, new RutasApi(fuente, "BTCUSDT").crearRouter(), "*");
        servidor.iniciar();
        puerto = servidor.puerto();
    }

    @AfterEach
    void detener() {
        servidor.detener(0);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> mapa(Object valor) {
        return (Map<String, Object>) valor;
    }

    private void assertError400(String rutaYConsulta, String fragmento) {
        HttpResponse<String> r = get(puerto, rutaYConsulta);
        assertEquals(400, r.statusCode(), r.body());
        String mensaje = (String) json(r).get("error");
        assertTrue(mensaje.contains(fragmento), "mensaje: " + mensaje);
    }

    // ---------- /api/senal ----------

    @Test
    void senalPorDefectoEsLaCombinadaConDecisionYPronostico() {
        HttpResponse<String> r = get(puerto, "/api/senal");
        assertEquals(200, r.statusCode());
        Map<String, Object> cuerpo = json(r);
        assertEquals("[simbolo, intervalo, estrategia, parametros, velasAnalizadas, decision, pronostico]",
                cuerpo.keySet().toString());
        assertEquals("combinada", cuerpo.get("estrategia"));
        assertEquals(200.0, cuerpo.get("velasAnalizadas"));

        Map<String, Object> decision = mapa(cuerpo.get("decision"));
        assertEquals("[tiempo, senal, precio, confianza, motivo]", decision.keySet().toString());
        assertEquals(600.0, decision.get("precio")); // cierre de la última vela de la FuenteFalsa

        Map<String, Object> pronostico = mapa(cuerpo.get("pronostico"));
        assertEquals("[direccion, confianza, justificacion, indicadores, aviso]", pronostico.keySet().toString());
        assertEquals(Pronostico.AVISO, pronostico.get("aviso"));
        assertEquals(6, mapa(pronostico.get("indicadores")).size());
    }

    @Test
    void senalDeUnaEstrategiaConSusParametros() {
        Map<String, Object> cuerpo = json(get(puerto, "/api/senal?estrategia=rsi&periodo=7&intervalo=4h&cantidad=50"));
        assertEquals("rsi", cuerpo.get("estrategia"));
        assertEquals("4h", cuerpo.get("intervalo"));
        assertEquals("{periodo=7.0, sobreventa=30.0, sobrecompra=70.0}", cuerpo.get("parametros").toString());
        // La FuenteFalsa siempre sube: RSI 100, en sobrecompra, sin señal de giro.
        assertEquals("MANTENER", mapa(cuerpo.get("decision")).get("senal"));
        assertEquals("LATERAL", mapa(cuerpo.get("pronostico")).get("direccion"));
    }

    @Test
    void laVelaQueTodaviaNoCierraSeDescarta() {
        ListaDoble<Vela> velas = FuenteFalsa.generarVelas(60, Intervalo.D1);
        long ahora = System.currentTimeMillis();
        velas.agregarFinal(new Vela(ahora - 1000, 700, 710, 690, 705, 1, ahora + Intervalo.D1.milisegundos()));
        fuente.setVelas(velas);
        Map<String, Object> cuerpo = json(get(puerto, "/api/senal?estrategia=cruce&cantidad=100"));
        assertEquals(60.0, cuerpo.get("velasAnalizadas"));
        assertEquals(160.0, mapa(cuerpo.get("decision")).get("precio")); // cierre de la vela 59, no 705
    }

    @Test
    void senalConParametrosInvalidosDa400() {
        assertError400("/api/senal?estrategia=magia", "Estrategia desconocida");
        assertError400("/api/senal?estrategia=cruce&corta=50&larga=20", "'larga'");
        assertError400("/api/senal?intervalo=7m", "'intervalo'");
        assertEquals(0, fuente.getLlamadasVelas());
    }

    // ---------- /api/backtest ----------

    @Test
    void backtestDevuelveResultadoValidacionYAviso() {
        HttpResponse<String> r = get(puerto, "/api/backtest?estrategia=cruce&capital=1000&comision=0.001&intervalo=1d&cantidad=1000");
        assertEquals(200, r.statusCode(), r.body());
        Map<String, Object> cuerpo = json(r);
        assertEquals("[simbolo, intervalo, estrategia, parametros, resultado, validacion, aviso]",
                cuerpo.keySet().toString());
        assertEquals(Pronostico.AVISO, cuerpo.get("aviso"));

        Map<String, Object> resultado = mapa(cuerpo.get("resultado"));
        assertEquals(1000.0, resultado.get("capitalInicial"));
        assertEquals(500.0, resultado.get("velasAnalizadas")); // la FuenteFalsa tiene 500
        // primera apertura 100, último cierre 600, comisión en compra y venta
        assertEquals(0.999 * 0.999 * 6 - 1, (Double) resultado.get("rentabilidadComprarYMantener"), 1e-9);
        assertTrue(resultado.containsKey("curvaCapital") && resultado.containsKey("operaciones"));

        Map<String, Object> validacion = mapa(cuerpo.get("validacion"));
        assertEquals(350.0, validacion.get("velasEntrenamiento"));
        assertEquals(150.0, validacion.get("velasPrueba"));
        assertEquals(9, ((Lista<?>) validacion.get("candidatos")).tamanio());
        assertEquals(150.0, mapa(validacion.get("prueba")).get("velasAnalizadas"));
    }

    @Test
    void backtestPorDefectoUsaLaCombinadaYSetentaPorCiento() {
        Map<String, Object> cuerpo = json(get(puerto, "/api/backtest?cantidad=300"));
        assertEquals("combinada", cuerpo.get("estrategia"));
        Map<String, Object> validacion = mapa(cuerpo.get("validacion"));
        assertEquals(0.7, validacion.get("fraccionEntrenamiento"));
        assertEquals(210.0, validacion.get("velasEntrenamiento"));
        assertEquals(4, ((Lista<?>) validacion.get("candidatos")).tamanio());
    }

    @Test
    void backtestConParametrosInvalidosDa400() {
        assertError400("/api/backtest?capital=0", "'capital'");
        assertError400("/api/backtest?capital=abc", "'capital'");
        assertError400("/api/backtest?comision=0.1", "'comision'");
        assertError400("/api/backtest?entrenamiento=0.95", "'entrenamiento'");
        assertError400("/api/backtest?cantidad=5000", "'cantidad'");
        assertError400("/api/backtest?estrategia=macd&lento=5&rapido=10", "'lento'");
        assertEquals(0, fuente.getLlamadasVelas());
    }

    @Test
    void siLaFuenteFallaResponde502() {
        fuente.setError(new MercadoException("caída"));
        assertEquals(502, get(puerto, "/api/backtest?estrategia=cruce").statusCode());
        assertEquals(502, get(puerto, "/api/senal").statusCode());
    }
}
