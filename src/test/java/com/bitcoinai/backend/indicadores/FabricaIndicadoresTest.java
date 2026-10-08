package com.bitcoinai.backend.indicadores;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;
import org.junit.jupiter.api.Test;

class FabricaIndicadoresTest {

    private static void assertInvalido(String fragmento, String nombre, Map<String, String> parametros) {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> FabricaIndicadores.crear(nombre, parametros));
        assertTrue(e.getMessage().contains(fragmento), "mensaje: " + e.getMessage());
    }

    @Test
    void creaCadaIndicadorConSusValoresPorDefecto() {
        assertEquals("{periodo=20}", assertInstanceOf(Sma.class, FabricaIndicadores.crear("sma")).parametros().toString());
        assertEquals("{periodo=20}", assertInstanceOf(Ema.class, FabricaIndicadores.crear("ema")).parametros().toString());
        assertEquals("{periodo=14}", assertInstanceOf(Rsi.class, FabricaIndicadores.crear("rsi")).parametros().toString());
        assertEquals("{rapido=12, lento=26, senal=9}",
                assertInstanceOf(Macd.class, FabricaIndicadores.crear("macd")).parametros().toString());
        assertEquals("{periodo=20, desviaciones=2.0}",
                assertInstanceOf(BandasBollinger.class, FabricaIndicadores.crear("bollinger")).parametros().toString());
        assertEquals("{periodo=20}",
                assertInstanceOf(Volatilidad.class, FabricaIndicadores.crear("volatilidad")).parametros().toString());
    }

    @Test
    void usaLosParametrosRecibidosEIgnoraLosAjenos() {
        Indicador rsi = FabricaIndicadores.crear(" RSI ", Map.of("periodo", "7", "intervalo", "1d"));
        assertEquals("rsi", rsi.nombre());
        assertEquals("{periodo=7}", rsi.parametros().toString());
        Indicador macd = FabricaIndicadores.crear("macd", Map.of("rapido", "5", "lento", "10", "senal", "3"));
        assertEquals("{rapido=5, lento=10, senal=3}", macd.parametros().toString());
        Indicador bollinger = FabricaIndicadores.crear("bollinger", Map.of("desviaciones", "1.5"));
        assertEquals("{periodo=20, desviaciones=1.5}", bollinger.parametros().toString());
    }

    @Test
    void nombreFaltanteODesconocido() {
        assertInvalido("Falta el parámetro 'indicador'", null, Map.of());
        assertInvalido("Falta el parámetro 'indicador'", " ", Map.of());
        assertInvalido("Indicador desconocido: 'adx'", "adx", Map.of());
        assertInvalido(FabricaIndicadores.NOMBRES, "adx", Map.of());
    }

    @Test
    void periodoDebeSerAlMenosDosYEntero() {
        assertInvalido("entre 2 y 1000", "sma", Map.of("periodo", "1"));
        assertInvalido("entre 2 y 1000", "ema", Map.of("periodo", "0"));
        assertInvalido("entre 2 y 1000", "rsi", Map.of("periodo", "1001"));
        assertInvalido("'periodo' inválido: 'abc'", "volatilidad", Map.of("periodo", "abc"));
        assertInvalido("'periodo' inválido", "sma", Map.of("periodo", "3.5"));
    }

    @Test
    void parametrosInvalidosDelMacdYBollinger() {
        assertInvalido("'lento' (12) debe ser mayor que 'rapido' (26)", "macd", Map.of("rapido", "26", "lento", "12"));
        assertInvalido("'senal' inválido", "macd", Map.of("senal", "1"));
        assertInvalido("'desviaciones' inválido", "bollinger", Map.of("desviaciones", "0"));
        assertInvalido("'desviaciones' inválido", "bollinger", Map.of("desviaciones", "x"));
    }

    @Test
    void periodoMayorQueLasVelasDaListaVaciaNoError() {
        Indicador sma = FabricaIndicadores.crear("sma", Map.of("periodo", "500"));
        assertTrue(sma.calcular(VelasPrueba.lineales(10, 1, 1)).estaVacia());
        assertTrue(FabricaIndicadores.crear("macd").calcularSeries(VelasPrueba.lineales(10, 1, 1))
                .get("senal").estaVacia());
    }
}
