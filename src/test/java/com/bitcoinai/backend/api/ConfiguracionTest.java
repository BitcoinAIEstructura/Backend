package com.bitcoinai.backend.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Map;
import org.junit.jupiter.api.Test;

class ConfiguracionTest {

    @Test
    void valoresPorDefecto() {
        Configuracion c = Configuracion.desde(Map.<String, String>of()::get);
        assertEquals(8080, c.puerto());
        assertEquals("https://api.binance.com", c.urlBaseBinance());
        assertEquals("*", c.origenPermitido());
        assertEquals(30, c.ttlCacheSegundos());
        assertEquals("BTCUSDT", c.simbolo());
        assertEquals(50, c.maxStreams());
        assertEquals("./data", c.dataDir());
    }

    @Test
    void leeMaxStreamsYDataDir() {
        Configuracion c = Configuracion.desde(Map.of("MAX_STREAMS", "5", "DATA_DIR", "/data")::get);
        assertEquals(5, c.maxStreams());
        assertEquals("/data", c.dataDir());
        assertThrows(IllegalArgumentException.class, () -> Configuracion.desde(Map.of("MAX_STREAMS", "0")::get));
        assertThrows(IllegalArgumentException.class, () -> Configuracion.desde(Map.of("MAX_STREAMS", "x")::get));
    }

    @Test
    void leeLasVariablesDefinidas() {
        Map<String, String> entorno = Map.of(
                "PORT", "3000",
                "BINANCE_BASE_URL", "https://data-api.binance.vision",
                "ORIGEN_PERMITIDO", "https://mi-panel.app",
                "TTL_CACHE_SEGUNDOS", "0",
                "SIMBOLO", " ethusdt ");
        Configuracion c = Configuracion.desde(entorno::get);
        assertEquals(3000, c.puerto());
        assertEquals("https://data-api.binance.vision", c.urlBaseBinance());
        assertEquals("https://mi-panel.app", c.origenPermitido());
        assertEquals(0, c.ttlCacheSegundos());
        assertEquals("ETHUSDT", c.simbolo());
    }

    @Test
    void valoresVaciosUsanElPorDefecto() {
        Configuracion c = Configuracion.desde(Map.of("PORT", " ", "ORIGEN_PERMITIDO", "")::get);
        assertEquals(8080, c.puerto());
        assertEquals("*", c.origenPermitido());
    }

    @Test
    void puertoInvalidoDaUnMensajeClaro() {
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> Configuracion.desde(Map.of("PORT", "abc")::get));
        assertTrue(e.getMessage().startsWith("PORT debe ser un número entero entre 0 y 65535"));
        assertThrows(IllegalArgumentException.class, () -> Configuracion.desde(Map.of("PORT", "70000")::get));
        assertThrows(IllegalArgumentException.class, () -> Configuracion.desde(Map.of("PORT", "-1")::get));
    }

    @Test
    void ttlYSimboloInvalidos() {
        assertThrows(IllegalArgumentException.class,
                () -> Configuracion.desde(Map.of("TTL_CACHE_SEGUNDOS", "-5")::get));
        assertThrows(IllegalArgumentException.class,
                () -> Configuracion.desde(Map.of("SIMBOLO", "BTC/USDT")::get));
    }
}
