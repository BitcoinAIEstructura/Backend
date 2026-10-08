package com.bitcoinai.backend.api;

import static com.bitcoinai.backend.api.ClienteHttpPrueba.get;
import static com.bitcoinai.backend.api.ClienteHttpPrueba.json;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.mercado.MercadoException;
import java.io.IOException;
import java.net.http.HttpResponse;
import java.util.Map;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/** Pruebas de GET /api/indicadores con una FuenteFalsa (velas siempre crecientes). */
class IndicadoresApiTest {

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

    private void assertError400(String consulta, String fragmento) {
        HttpResponse<String> r = get(puerto, "/api/indicadores" + consulta);
        assertEquals(400, r.statusCode(), r.body());
        String mensaje = (String) json(r).get("error");
        assertTrue(mensaje.contains(fragmento), "mensaje: " + mensaje);
    }

    @Test
    void rsiDevuelveLaSerieYLasVelasUsadas() {
        HttpResponse<String> r = get(puerto, "/api/indicadores?indicador=rsi&periodo=14&intervalo=1d&cantidad=200");
        assertEquals(200, r.statusCode());
        Map<String, Object> cuerpo = json(r);
        assertEquals("[simbolo, intervalo, indicador, parametros, series, maximaCaida, cantidad, velas]",
                cuerpo.keySet().toString());
        assertEquals("rsi", cuerpo.get("indicador"));
        assertEquals("{periodo=14.0}", cuerpo.get("parametros").toString());
        assertEquals(200, ((Lista<?>) cuerpo.get("velas")).tamanio());

        Lista<?> valores = (Lista<?>) mapa(cuerpo.get("series")).get("valor");
        assertEquals(186, valores.tamanio()); // 200 − 14 de calentamiento
        Map<String, Object> ultimo = mapa(valores.ultimo());
        assertEquals(100.0, ultimo.get("valor")); // la FuenteFalsa siempre sube
        Map<String, Object> ultimaVela = mapa(((Lista<?>) cuerpo.get("velas")).ultimo());
        assertEquals(ultimaVela.get("tiempoApertura"), ultimo.get("tiempo"));
    }

    @Test
    void rsiSinPeriodoUsaCatorce() {
        Map<String, Object> cuerpo = json(get(puerto, "/api/indicadores?indicador=rsi&cantidad=50"));
        assertEquals("{periodo=14.0}", cuerpo.get("parametros").toString());
        assertEquals(36, ((Lista<?>) mapa(cuerpo.get("series")).get("valor")).tamanio());
    }

    @Test
    void macdYBollingerDevuelvenTresSeries() {
        Map<String, Object> macd = json(get(puerto, "/api/indicadores?indicador=macd&cantidad=100"));
        assertEquals("[macd, senal, histograma]", mapa(macd.get("series")).keySet().toString());
        assertEquals("{rapido=12.0, lento=26.0, senal=9.0}", macd.get("parametros").toString());

        Map<String, Object> bollinger = json(get(puerto, "/api/indicadores?indicador=bollinger&periodo=10&desviaciones=1.5"));
        assertEquals("[media, superior, inferior]", mapa(bollinger.get("series")).keySet().toString());
    }

    @Test
    void cadaIndicadorDeLaFabricaResponde200() {
        for (String nombre : new String[] {"sma", "ema", "rsi", "macd", "bollinger", "volatilidad"}) {
            assertEquals(200, get(puerto, "/api/indicadores?indicador=" + nombre + "&cantidad=60").statusCode(), nombre);
        }
    }

    @Test
    void incluyeLaMaximaCaidaDeLasVelas() {
        Map<String, Object> caida = mapa(json(get(puerto, "/api/indicadores?indicador=sma")).get("maximaCaida"));
        assertEquals(0.0, caida.get("caidaMaxima")); // la FuenteFalsa nunca baja
    }

    @Test
    void periodoMayorQueLasVelasDevuelveSerieVacia() {
        Map<String, Object> cuerpo = json(get(puerto, "/api/indicadores?indicador=sma&periodo=500&cantidad=10"));
        assertEquals(0, ((Lista<?>) mapa(cuerpo.get("series")).get("valor")).tamanio());
        assertEquals(10, ((Lista<?>) cuerpo.get("velas")).tamanio());
    }

    @Test
    void parametrosInvalidosDan400ConElMotivoSinConsultarLaFuente() {
        assertError400("", "Falta el parámetro 'indicador'");
        assertError400("?indicador=adx", "Indicador desconocido");
        assertError400("?indicador=rsi&periodo=1", "entre 2 y 1000");
        assertError400("?indicador=rsi&periodo=abc", "'periodo' inválido");
        assertError400("?indicador=macd&rapido=30&lento=20", "'lento'");
        assertError400("?indicador=rsi&intervalo=2h", "'intervalo' inválido");
        assertError400("?indicador=rsi&cantidad=0", "'cantidad' inválido");
        assertEquals(0, fuente.getLlamadasVelas());
    }

    @Test
    void siLaFuenteFallaResponde502() {
        fuente.setError(new MercadoException("caída"));
        HttpResponse<String> r = get(puerto, "/api/indicadores?indicador=rsi");
        assertEquals(502, r.statusCode());
        assertEquals("{\"error\":\"Fuente de mercado no disponible\"}", r.body());
    }
}
