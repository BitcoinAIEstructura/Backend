package com.bitcoinai.backend.simulacion;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;

import com.bitcoinai.backend.estrategia.Decision;
import com.bitcoinai.backend.estrategia.Senal;
import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.mercado.MercadoException;
import com.bitcoinai.backend.modelo.Intervalo;
import org.junit.jupiter.api.Test;

/** El libro y el bot avisan sus cambios por la interfaz PublicadorEventos, sin saber nada de HTTP. */
class EventosSimulacionTest {

    /** Publicador de prueba que anota todo lo que recibe. */
    static final class Anotador implements PublicadorEventos {
        final Lista<String> tipos = new Lista<>();
        final Lista<Object> datos = new Lista<>();

        @Override
        public synchronized void publicar(String tipo, Object dato) {
            tipos.agregar(tipo);
            datos.agregar(dato);
        }

        synchronized String resumen() {
            StringBuilder sb = new StringBuilder();
            int i = 0;
            for (String tipo : tipos) {
                Object dato = datos.obtener(i++);
                sb.append(tipo);
                if (dato instanceof Orden orden) {
                    sb.append(':').append(orden.estado());
                } else if (dato instanceof Decision decision) {
                    sb.append(':').append(decision.senal());
                }
                sb.append(' ');
            }
            return sb.toString().trim();
        }
    }

    private final FuenteFalsa fuente = new FuenteFalsa(FuenteFalsa.generarVelas(100, Intervalo.H1), 100.0);
    private final LibroDeOrdenes libro = new LibroDeOrdenes(new Cartera(), fuente, "BTCUSDT");
    private final Anotador anotador = new Anotador();

    @Test
    void elLibroAvisaCadaCambioDeEstadoYDeCartera() {
        libro.usarPublicador(anotador);
        libro.crearCompra(100, null);
        libro.procesarSiguiente();
        libro.crearCompra(50, null);
        libro.cancelar(2);
        libro.crearCompra(99_999, null);
        libro.procesarSiguiente();
        assertEquals("orden:PENDIENTE orden:PROCESANDO orden:EJECUTADA cartera "
                + "orden:PENDIENTE orden:CANCELADA "
                + "orden:PENDIENTE orden:PROCESANDO orden:RECHAZADA", anotador.resumen());
        EstadoCartera cartera = assertInstanceOf(EstadoCartera.class, anotador.datos.obtener(3));
        assertEquals(9_900, cartera.saldoUsdt(), 1e-9);
    }

    @Test
    void siFallaElPrecioAvisaQueLaOrdenVolvioAPendiente() {
        libro.usarPublicador(anotador);
        libro.crearCompra(100, null);
        fuente.setError(new MercadoException("caída"));
        try {
            libro.procesarSiguiente();
        } catch (MercadoException esperado) {
            // la orden vuelve a la cola
        }
        assertEquals("orden:PENDIENTE orden:PROCESANDO orden:PENDIENTE", anotador.resumen());
    }

    @Test
    void elBotPublicaLaSenalSoloCuandoCambia() {
        EstrategiaManual estrategia = new EstrategiaManual();
        BotSimulado bot = new BotSimulado(libro, fuente, estrategia, "BTCUSDT");
        bot.usarPublicador(anotador);
        bot.ejecutarCiclo();                  // primera decisión: MANTENER → se publica
        bot.ejecutarCiclo();                  // igual → no
        estrategia.decir(Senal.COMPRAR);
        bot.ejecutarCiclo();                  // cambia → se publica
        bot.ejecutarCiclo();                  // igual → no
        estrategia.decir(Senal.MANTENER);
        bot.ejecutarCiclo();                  // cambia → se publica
        assertEquals("senal:MANTENER senal:COMPRAR senal:MANTENER", anotador.resumen());
    }
}
