package com.bitcoinai.backend.simulacion;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.mercado.FuenteDeMercado;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.mercado.MercadoException;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;

class LibroDeOrdenesTest {

    private final FuenteFalsa fuente = new FuenteFalsa(new ListaDoble<>(), 100.0);
    private final AtomicLong reloj = new AtomicLong(1_000);
    private final LibroDeOrdenes libro = new LibroDeOrdenes(new Cartera(), fuente, "BTCUSDT", 0.001,
            reloj::incrementAndGet);

    private static String ids(Lista<Orden> ordenes) {
        StringBuilder sb = new StringBuilder();
        for (Orden o : ordenes) {
            sb.append(o.id()).append(' ');
        }
        return sb.toString().trim();
    }

    // ---------- FIFO ----------

    @Test
    void lasOrdenesSeEjecutanEnOrdenDeLlegada() {
        libro.crearCompra(100, null);
        libro.crearCompra(200, null);
        libro.crearCompra(300, null);
        assertEquals("1 2 3", ids(libro.ordenes(EstadoOrden.PENDIENTE)));

        assertEquals(1, libro.procesarSiguiente().orElseThrow().id());
        assertEquals(2, libro.procesarSiguiente().orElseThrow().id());
        assertEquals(3, libro.procesarSiguiente().orElseThrow().id());
        assertTrue(libro.procesarSiguiente().isEmpty());

        Lista<Orden> ejecutadas = libro.ordenes(EstadoOrden.EJECUTADA);
        assertEquals("1 2 3", ids(ejecutadas));
        assertTrue(ejecutadas.obtener(0).ejecutadaEn() < ejecutadas.obtener(1).ejecutadaEn());
    }

    @Test
    void ordenNuevaQuedaPendienteConSusDatos() {
        Orden orden = libro.crearCompra(500, "  ");
        assertEquals(1, orden.id());
        assertEquals(TipoOrden.COMPRA, orden.tipo());
        assertEquals(500.0, orden.monto());
        assertEquals(EstadoOrden.PENDIENTE, orden.estado());
        assertEquals("manual", orden.motivo());
        assertNull(orden.ejecutadaEn());
        assertNull(orden.precioEjecucion());
        assertEquals(1, libro.cantidadPendientes());
    }

    // ---------- ejecución con comisión ----------

    @Test
    void compraYVentaConComisionActualizanLaCartera() {
        libro.crearCompra(500, null);
        Orden compra = libro.procesarSiguiente().orElseThrow();
        assertEquals(EstadoOrden.EJECUTADA, compra.estado());
        assertEquals(100.0, compra.precioEjecucion());
        assertEquals(0.5, compra.comision(), 1e-12);
        assertEquals(4.995, compra.cantidadBtc(), 1e-12);

        EstadoCartera tras = libro.estadoCartera(100);
        assertEquals(9_500, tras.saldoUsdt(), 1e-9);
        assertEquals(4.995, tras.btc(), 1e-12);

        fuente.setPrecio(120);
        libro.crearVenta(120, null); // 1 BTC
        Orden venta = libro.procesarSiguiente().orElseThrow();
        assertEquals(1.0, venta.cantidadBtc(), 1e-12);
        assertEquals(0.12, venta.comision(), 1e-12);

        EstadoCartera fin = libro.estadoCartera(120);
        assertEquals(3.995, fin.btc(), 1e-12);
        assertEquals(9_500 + 120 - 0.12, fin.saldoUsdt(), 1e-9);
        assertEquals(0.62, fin.comisionesPagadas(), 1e-9);
    }

    @Test
    void ventaDeTodoGuardaElMontoObtenido() {
        libro.crearCompra(1000, null);
        libro.procesarSiguiente();
        fuente.setPrecio(110);
        libro.crearVentaTotal("salida");
        Orden venta = libro.procesarSiguiente().orElseThrow();
        assertTrue(venta.todo());
        assertEquals(9.99 * 110, venta.monto(), 1e-9);
        assertEquals(0, libro.estadoCartera(110).btc());
    }

    // ---------- rechazos ----------

    @Test
    void compraSinSaldoSuficienteSeRechazaConMotivo() {
        libro.crearCompra(20_000, null);
        Orden orden = libro.procesarSiguiente().orElseThrow();
        assertEquals(EstadoOrden.RECHAZADA, orden.estado());
        assertEquals("Saldo insuficiente: la compra necesita 20000.00 USDT y hay 10000.00", orden.detalle());
        assertEquals(100.0, orden.precioEjecucion());
        assertEquals(10_000, libro.estadoCartera(100).saldoUsdt());
        assertEquals(TipoEvento.ORDEN_RECHAZADA, libro.historial(1).primero().tipo());
    }

    @Test
    void ventaSinBtcSeRechaza() {
        libro.crearVenta(50, null);
        libro.crearVentaTotal(null);
        assertEquals(EstadoOrden.RECHAZADA, libro.procesarSiguiente().orElseThrow().estado());
        assertEquals("No hay BTC para vender", libro.procesarSiguiente().orElseThrow().detalle());
    }

    // ---------- cancelar y deshacer ----------

    @Test
    void cancelarUnaOrdenDelMedioConservaElOrdenDeLasDemas() {
        libro.crearCompra(100, null);
        libro.crearCompra(200, null);
        libro.crearCompra(300, null);
        libro.crearCompra(400, null);
        Orden cancelada = libro.cancelar(2);
        assertEquals(EstadoOrden.CANCELADA, cancelada.estado());
        assertEquals("1 3 4", ids(libro.ordenes(EstadoOrden.PENDIENTE)));
        assertEquals(1, libro.procesarSiguiente().orElseThrow().id());
        assertEquals(3, libro.procesarSiguiente().orElseThrow().id());
        assertEquals(4, libro.procesarSiguiente().orElseThrow().id());
        assertEquals("2", ids(libro.ordenes(EstadoOrden.CANCELADA)));
    }

    @Test
    void cancelarAlgoQueNoEstaPendienteFalla() {
        libro.crearCompra(100, null);
        libro.procesarSiguiente();
        OperacionInvalidaException e = assertThrows(OperacionInvalidaException.class, () -> libro.cancelar(1));
        assertEquals("La orden #1 ya no está pendiente: está EJECUTADA", e.getMessage());
        assertThrows(OrdenNoEncontradaException.class, () -> libro.cancelar(99));
    }

    @Test
    void deshacerQuitaLaUltimaCreadaYLuegoLaAnterior() {
        libro.crearCompra(100, null);
        libro.crearCompra(200, null);
        libro.crearCompra(300, null);
        Orden deshecha = libro.deshacerUltimaOrden().orElseThrow();
        assertEquals(3, deshecha.id());
        assertEquals(EstadoOrden.CANCELADA, deshecha.estado());
        assertEquals("1 2", ids(libro.ordenes(EstadoOrden.PENDIENTE)));
        assertEquals(2, libro.deshacerUltimaOrden().orElseThrow().id());
        assertEquals("1", ids(libro.ordenes(EstadoOrden.PENDIENTE)));
        assertEquals(TipoEvento.ORDEN_DESHECHA, libro.historial(1).primero().tipo());
    }

    @Test
    void deshacerNoHaceNadaSiLaUltimaYaSeEjecuto() {
        assertTrue(libro.deshacerUltimaOrden().isEmpty());
        libro.crearCompra(100, null);
        libro.procesarSiguiente();
        assertTrue(libro.deshacerUltimaOrden().isEmpty());
        assertEquals("1", ids(libro.ordenes(EstadoOrden.EJECUTADA)));
    }

    // ---------- historial ----------

    @Test
    void historialDevuelveLoMasRecientePrimeroSinBorrarlo() {
        libro.crearCompra(100, null);
        libro.procesarSiguiente();
        libro.crearCompra(200, null);
        libro.cancelar(2);
        Lista<Evento> eventos = libro.historial(10);
        assertEquals(4, eventos.tamanio());
        assertEquals(TipoEvento.ORDEN_CANCELADA, eventos.obtener(0).tipo());
        assertEquals(TipoEvento.ORDEN_CREADA, eventos.obtener(1).tipo());
        assertEquals(TipoEvento.ORDEN_EJECUTADA, eventos.obtener(2).tipo());
        assertEquals(TipoEvento.ORDEN_CREADA, eventos.obtener(3).tipo());
        assertEquals(2L, eventos.obtener(0).idOrden());
        // Leerlo no lo modifica: la segunda lectura da lo mismo.
        assertEquals(4, libro.historial(10).tamanio());
        assertEquals(2, libro.historial(2).tamanio());
        assertEquals(TipoEvento.ORDEN_CANCELADA, libro.historial(2).primero().tipo());
    }

    // ---------- fallos y estado PROCESANDO ----------

    @Test
    void siFallaElPrecioLaOrdenVuelveAlFrenteDeLaCola() {
        libro.crearCompra(100, null);
        libro.crearCompra(200, null);
        fuente.setError(new MercadoException("Binance caído"));
        assertThrows(MercadoException.class, libro::procesarSiguiente);
        assertEquals("1 2", ids(libro.ordenes(EstadoOrden.PENDIENTE)));
        fuente.setError(null);
        assertEquals(1, libro.procesarSiguiente().orElseThrow().id());
    }

    @Test
    void mientrasSeConsultaElPrecioLaOrdenEstaProcesandoYNoSePuedeCancelar() throws Exception {
        CountDownLatch entro = new CountDownLatch(1);
        CountDownLatch liberar = new CountDownLatch(1);
        FuenteDeMercado lenta = new FuenteDeMercado() {
            @Override
            public ListaDoble<Vela> obtenerVelas(String simbolo, Intervalo intervalo, int cantidad) {
                return new ListaDoble<>();
            }

            @Override
            public double obtenerPrecioActual(String simbolo) {
                entro.countDown();
                try {
                    liberar.await(5, TimeUnit.SECONDS);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
                return 100;
            }
        };
        LibroDeOrdenes libroLento = new LibroDeOrdenes(new Cartera(), lenta, "BTCUSDT");
        libroLento.crearCompra(100, null);
        ExecutorService hilo = Executors.newSingleThreadExecutor();
        try {
            Future<?> proceso = hilo.submit(libroLento::procesarSiguiente);
            assertTrue(entro.await(5, TimeUnit.SECONDS));
            // Mientras tanto se puede consultar y crear sin bloquearse.
            assertEquals("1", ids(libroLento.ordenes(EstadoOrden.PROCESANDO)));
            libroLento.crearCompra(50, null);
            OperacionInvalidaException e = assertThrows(OperacionInvalidaException.class, () -> libroLento.cancelar(1));
            assertTrue(e.getMessage().contains("se está procesando"));
            liberar.countDown();
            proceso.get(5, TimeUnit.SECONDS);
            assertEquals("1", ids(libroLento.ordenes(EstadoOrden.EJECUTADA)));
            assertEquals("2", ids(libroLento.ordenes(EstadoOrden.PENDIENTE)));
        } finally {
            liberar.countDown();
            hilo.shutdownNow();
        }
    }

    // ---------- concurrencia ----------

    @Test
    void variosHilosCreandoALaVezNoPierdenNingunaOrden() throws Exception {
        int hilos = 8;
        int porHilo = 250;
        ExecutorService ejecutor = Executors.newFixedThreadPool(hilos);
        CountDownLatch largada = new CountDownLatch(1);
        try {
            for (int h = 0; h < hilos; h++) {
                ejecutor.submit(() -> {
                    largada.await();
                    for (int i = 0; i < porHilo; i++) {
                        libro.crearCompra(1, "hilo");
                    }
                    return null;
                });
            }
            largada.countDown();
            ejecutor.shutdown();
            assertTrue(ejecutor.awaitTermination(10, TimeUnit.SECONDS));
        } finally {
            ejecutor.shutdownNow();
        }
        assertEquals(hilos * porHilo, libro.cantidadPendientes());
        Set<Long> distintos = new HashSet<>();
        for (Orden o : libro.ordenes(EstadoOrden.PENDIENTE)) {
            distintos.add(o.id());
        }
        assertEquals(hilos * porHilo, distintos.size());
        assertEquals(hilos * porHilo, libro.historial(10_000).tamanio());
    }

    @Test
    void crearYProcesarALaVezDesdeVariosHilosCuadraLasCuentas() throws Exception {
        ExecutorService ejecutor = Executors.newFixedThreadPool(6);
        try {
            for (int h = 0; h < 3; h++) {
                ejecutor.submit(() -> {
                    for (int i = 0; i < 100; i++) {
                        libro.crearCompra(10, null);
                    }
                });
                ejecutor.submit(() -> {
                    for (int i = 0; i < 150; i++) {
                        libro.procesarSiguiente();
                    }
                });
            }
            ejecutor.shutdown();
            assertTrue(ejecutor.awaitTermination(10, TimeUnit.SECONDS));
        } finally {
            ejecutor.shutdownNow();
        }
        while (libro.procesarSiguiente().isPresent()) {
            // vacía lo que haya quedado
        }
        assertEquals(300, libro.ordenes(EstadoOrden.EJECUTADA).tamanio());
        assertEquals(10_000 - 3000, libro.estadoCartera(100).saldoUsdt(), 1e-6);
    }

    // ---------- validación ----------

    @Test
    void datosInvalidosAlCrear() {
        assertThrows(IllegalArgumentException.class, () -> libro.crearCompra(0, null));
        assertThrows(IllegalArgumentException.class, () -> libro.crearCompra(-5, null));
        assertThrows(IllegalArgumentException.class, () -> libro.crearOrden(TipoOrden.COMPRA, null, true, null));
        assertThrows(IllegalArgumentException.class, () -> libro.crearOrden(TipoOrden.VENTA, 10.0, true, null));
        assertThrows(IllegalArgumentException.class, () -> libro.crearOrden(TipoOrden.VENTA, Double.NaN, false, null));
        assertThrows(OrdenNoEncontradaException.class, () -> libro.obtener(5));
        assertEquals(0, libro.cantidadPendientes());
    }
}
