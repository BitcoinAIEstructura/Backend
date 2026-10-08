package com.bitcoinai.backend.mercado;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;

class CacheMercadoTest {

    private final FuenteFalsa fuente = new FuenteFalsa();
    private final AtomicLong reloj = new AtomicLong(1_000);
    private final CacheMercado cache = new CacheMercado(fuente, Duration.ofSeconds(30), reloj::get);

    @Test
    void segundaLlamadaDentroDelTtlNoConsultaLaFuente() {
        ListaDoble<Vela> primera = cache.obtenerVelas("BTCUSDT", Intervalo.D1, 10);
        reloj.addAndGet(29_999);
        ListaDoble<Vela> segunda = cache.obtenerVelas("BTCUSDT", Intervalo.D1, 10);
        assertEquals(1, fuente.getLlamadasVelas());
        assertEquals(10, segunda.tamanio());
        assertEquals(primera.ultimo(), segunda.ultimo());
    }

    @Test
    void despuesDelTtlVuelveAConsultarLaFuente() {
        cache.obtenerVelas("BTCUSDT", Intervalo.D1, 10);
        reloj.addAndGet(30_000);
        cache.obtenerVelas("BTCUSDT", Intervalo.D1, 10);
        assertEquals(2, fuente.getLlamadasVelas());
    }

    @Test
    void parametrosDistintosSeGuardanPorSeparado() {
        cache.obtenerVelas("BTCUSDT", Intervalo.D1, 10);
        cache.obtenerVelas("BTCUSDT", Intervalo.D1, 20);
        cache.obtenerVelas("BTCUSDT", Intervalo.H1, 10);
        cache.obtenerVelas("ETHUSDT", Intervalo.D1, 10);
        cache.obtenerVelas("BTCUSDT", Intervalo.D1, 20);
        assertEquals(4, fuente.getLlamadasVelas());
    }

    @Test
    void elPrecioTambienSeGuarda() {
        assertEquals(100.0, cache.obtenerPrecioActual("BTCUSDT"));
        fuente.setPrecio(200.0);
        assertEquals(100.0, cache.obtenerPrecioActual("BTCUSDT"));
        assertEquals(1, fuente.getLlamadasPrecio());
        reloj.addAndGet(30_000);
        assertEquals(200.0, cache.obtenerPrecioActual("BTCUSDT"));
    }

    @Test
    void losErroresNoSeGuardan() {
        fuente.setError(new MercadoException("caída"));
        assertThrows(MercadoException.class, () -> cache.obtenerVelas("BTCUSDT", Intervalo.D1, 5));
        fuente.setError(null);
        assertEquals(5, cache.obtenerVelas("BTCUSDT", Intervalo.D1, 5).tamanio());
        assertEquals(2, fuente.getLlamadasVelas());
    }

    @Test
    void modificarLaListaDevueltaNoDaniaLaCache() {
        ListaDoble<Vela> primera = cache.obtenerVelas("BTCUSDT", Intervalo.D1, 10);
        primera.vaciar();
        assertEquals(10, cache.obtenerVelas("BTCUSDT", Intervalo.D1, 10).tamanio());
        assertEquals(1, fuente.getLlamadasVelas());
    }

    @Test
    void ttlCeroDesactivaLaCache() {
        CacheMercado sinCache = new CacheMercado(fuente, Duration.ZERO, reloj::get);
        sinCache.obtenerPrecioActual("BTCUSDT");
        sinCache.obtenerPrecioActual("BTCUSDT");
        assertEquals(2, fuente.getLlamadasPrecio());
    }

    @Test
    void parametrosDelConstructorInvalidos() {
        assertThrows(IllegalArgumentException.class, () -> new CacheMercado(fuente, Duration.ofSeconds(-1)));
        assertThrows(NullPointerException.class, () -> new CacheMercado(null, Duration.ofSeconds(1)));
    }
}
