package com.bitcoinai.backend.simulacion;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estrategia.Senal;
import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.mercado.MercadoException;
import com.bitcoinai.backend.modelo.Intervalo;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

class BotSimuladoTest {

    private final FuenteFalsa fuente = new FuenteFalsa(FuenteFalsa.generarVelas(300, Intervalo.H1), 100.0);
    private final LibroDeOrdenes libro = new LibroDeOrdenes(new Cartera(), fuente, "BTCUSDT");
    private final EstrategiaManual estrategia = new EstrategiaManual();
    private final BotSimulado bot = new BotSimulado(libro, fuente, estrategia, "BTCUSDT");

    @AfterEach
    void detener() {
        bot.detener();
    }

    private EstadoCartera cartera() {
        return libro.estadoCartera(100);
    }

    private boolean hayEvento(TipoEvento tipo) {
        for (Evento e : libro.historial(100)) {
            if (e.tipo() == tipo) {
                return true;
            }
        }
        return false;
    }

    // ---------- decisiones ----------

    @Test
    void conComprarYSinPosicionCompraElVeintePorCientoDelSaldo() {
        estrategia.decir(Senal.COMPRAR);
        bot.ejecutarCiclo();
        Lista<Orden> ejecutadas = libro.ordenes(EstadoOrden.EJECUTADA);
        assertEquals(1, ejecutadas.tamanio());
        Orden compra = ejecutadas.primero();
        assertEquals(TipoOrden.COMPRA, compra.tipo());
        assertEquals(2_000, compra.monto(), 1e-9);
        assertTrue(compra.motivo().startsWith("señal del bot: "), compra.motivo());
        assertEquals(8_000, cartera().saldoUsdt(), 1e-9);
        assertTrue(cartera().btc() > 0);
    }

    @Test
    void conComprarYConPosicionNoCompraOtraVez() {
        estrategia.decir(Senal.COMPRAR);
        bot.ejecutarCiclo();
        bot.ejecutarCiclo();
        assertEquals(1, libro.ordenes(null).tamanio());
    }

    @Test
    void conVenderYConPosicionVendeTodo() {
        estrategia.decir(Senal.COMPRAR);
        bot.ejecutarCiclo();
        estrategia.decir(Senal.VENDER);
        bot.ejecutarCiclo();
        Orden venta = libro.ordenes(EstadoOrden.EJECUTADA).ultimo();
        assertEquals(TipoOrden.VENTA, venta.tipo());
        assertTrue(venta.todo());
        assertEquals(0, cartera().btc());
    }

    @Test
    void conVenderSinPosicionOMantenerNoHaceNada() {
        estrategia.decir(Senal.VENDER);
        bot.ejecutarCiclo();
        estrategia.decir(Senal.MANTENER);
        bot.ejecutarCiclo();
        assertEquals(0, libro.ordenes(null).tamanio());
        assertEquals(10_000, cartera().saldoUsdt());
    }

    @Test
    void cadaDecisionQuedaEnElHistorialConSuMotivo() {
        estrategia.decir(Senal.MANTENER);
        bot.ejecutarCiclo();
        Evento evento = libro.historial(1).primero();
        assertEquals(TipoEvento.DECISION_BOT, evento.tipo());
        assertEquals("El bot decidió MANTENER (confianza 0.25): la prueba pidió MANTENER", evento.descripcion());
        assertEquals(Senal.MANTENER, bot.estado().ultimaDecision().senal());
        assertEquals(1, bot.estado().ciclos());
    }

    // ---------- stop-loss y take-profit ----------

    @Test
    void stopLossVendeTodoAunqueLaEstrategiaDigaComprar() {
        estrategia.decir(Senal.COMPRAR);
        bot.ejecutarCiclo();                     // compra a 100 (costo promedio 100,1 con comisión)
        fuente.setPrecio(95);                    // −5,09 % desde el costo
        bot.ejecutarCiclo();
        Orden venta = libro.ordenes(EstadoOrden.EJECUTADA).ultimo();
        assertEquals(TipoOrden.VENTA, venta.tipo());
        assertTrue(venta.motivo().startsWith("stop-loss"), venta.motivo());
        assertEquals(0, libro.estadoCartera(95).btc());
        assertTrue(hayEvento(TipoEvento.STOP_LOSS));
    }

    @Test
    void sinLlegarAlStopLossNoVende() {
        estrategia.decir(Senal.COMPRAR);
        bot.ejecutarCiclo();
        fuente.setPrecio(96);                    // −4,1 %
        estrategia.decir(Senal.MANTENER);
        bot.ejecutarCiclo();
        assertTrue(libro.estadoCartera(96).btc() > 0);
    }

    @Test
    void takeProfitVendeTodoAlGanarDiezPorCiento() {
        estrategia.decir(Senal.COMPRAR);
        bot.ejecutarCiclo();
        fuente.setPrecio(111);                   // +10,9 % desde 100,1
        estrategia.decir(Senal.MANTENER);
        bot.ejecutarCiclo();
        Orden venta = libro.ordenes(EstadoOrden.EJECUTADA).ultimo();
        assertTrue(venta.motivo().startsWith("take-profit"), venta.motivo());
        assertTrue(hayEvento(TipoEvento.TAKE_PROFIT));
        assertTrue(libro.estadoCartera(111).gananciaRealizada() > 0);
    }

    // ---------- errores ----------

    @Test
    void unErrorDeLaFuenteQuedaRegistradoSinRomperElBot() {
        fuente.setError(new MercadoException("Binance no responde"));
        bot.ejecutarCiclo();
        assertEquals("Binance no responde", bot.estado().ultimoError());
        assertTrue(hayEvento(TipoEvento.ERROR_BOT));
        fuente.setError(null);
        bot.ejecutarCiclo();
        assertNull(bot.estado().ultimoError());
        assertEquals(2, bot.estado().ciclos());
    }

    @Test
    void elBotProcesaTambienLasOrdenesManualesPendientes() {
        libro.crearCompra(100, "manual");
        bot.ejecutarCiclo();
        assertEquals(0, libro.cantidadPendientes());
        assertEquals(1, libro.ordenes(EstadoOrden.EJECUTADA).tamanio());
    }

    // ---------- iniciar y detener ----------

    @Test
    void iniciarEjecutaCiclosPeriodicosYDetenerLosPara() throws InterruptedException {
        ConfiguracionBot rapido = new ConfiguracionBot(1, "1h", 50, 0.2, 0.05, 0.1);
        EstadoBot estado = bot.iniciar(rapido);
        assertTrue(estado.activo());
        assertEquals("manual", estado.estrategia());
        long limite = System.currentTimeMillis() + 5_000;
        while (bot.estado().ciclos() < 2 && System.currentTimeMillis() < limite) {
            Thread.sleep(20);
        }
        assertTrue(bot.estado().ciclos() >= 2, "debía ejecutar al menos dos ciclos");
        assertThrows(IllegalStateException.class, () -> bot.iniciar(rapido));

        EstadoBot detenido = bot.detener();
        assertFalse(detenido.activo());
        long ciclos = bot.estado().ciclos();
        Thread.sleep(1_200);
        assertTrue(bot.estado().ciclos() <= ciclos + 1, "no debía seguir ejecutando ciclos");
        assertTrue(hayEvento(TipoEvento.BOT_INICIADO));
        assertTrue(hayEvento(TipoEvento.BOT_DETENIDO));
        assertFalse(bot.detener().activo()); // detener dos veces no falla
    }

    @Test
    void configuracionInvalida() {
        assertThrows(IllegalArgumentException.class, () -> new ConfiguracionBot(0, "1h", 200, 0.2, 0.05, 0.1));
        assertThrows(IllegalArgumentException.class, () -> new ConfiguracionBot(60, "2h", 200, 0.2, 0.05, 0.1));
        assertThrows(IllegalArgumentException.class, () -> new ConfiguracionBot(60, "1h", 1, 0.2, 0.05, 0.1));
        assertThrows(IllegalArgumentException.class, () -> new ConfiguracionBot(60, "1h", 200, 0, 0.05, 0.1));
        assertThrows(IllegalArgumentException.class, () -> new ConfiguracionBot(60, "1h", 200, 0.2, 1, 0.1));
        assertThrows(IllegalArgumentException.class, () -> new ConfiguracionBot(60, "1h", 200, 0.2, 0.05, 0));
        assertEquals(new ConfiguracionBot(60, "1h", 200, 0.2, 0.05, 0.1), ConfiguracionBot.porDefecto());
    }
}
