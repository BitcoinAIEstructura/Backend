package com.bitcoinai.backend.persistencia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.simulacion.Cartera;
import com.bitcoinai.backend.simulacion.EstadoCartera;
import com.bitcoinai.backend.simulacion.EstadoOrden;
import com.bitcoinai.backend.simulacion.Evento;
import com.bitcoinai.backend.simulacion.LibroDeOrdenes;
import com.bitcoinai.backend.simulacion.Orden;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** El libro de órdenes guarda después de cada cambio y, al recargar, queda exactamente igual. */
class PersistenciaLibroTest {

    @TempDir
    Path carpeta;

    private final FuenteFalsa fuente = new FuenteFalsa(new ListaDoble<>(), 100.0);

    private LibroDeOrdenes libroNuevo() {
        LibroDeOrdenes libro = new LibroDeOrdenes(new Cartera(), fuente, "BTCUSDT");
        libro.usarAlmacen(new AlmacenArchivos(carpeta));
        return libro;
    }

    private static String ids(Lista<Orden> ordenes) {
        StringBuilder sb = new StringBuilder();
        for (Orden o : ordenes) {
            sb.append(o.id()).append(' ');
        }
        return sb.toString().trim();
    }

    private static String eventos(Lista<Evento> eventos) {
        StringBuilder sb = new StringBuilder();
        for (Evento e : eventos) {
            sb.append(e.tipo()).append('#').append(e.idOrden()).append(' ');
        }
        return sb.toString().trim();
    }

    @Test
    void idaYVueltaConservaElOrdenDeLaColaYDeLaPila() {
        LibroDeOrdenes antes = libroNuevo();
        antes.crearCompra(500, null);
        antes.procesarSiguiente();                // #1 ejecutada
        antes.crearCompra(100, "segunda");        // #2
        antes.crearCompra(200, null);             // #3
        antes.crearCompra(300, null);             // #4
        antes.cancelar(3);                        // cola: 2, 4
        EstadoCartera carteraAntes = antes.estadoCartera(100);
        String historialAntes = eventos(antes.historial(100));

        LibroDeOrdenes despues = libroNuevo();     // simula reiniciar el servidor

        assertEquals("2 4", ids(despues.ordenes(EstadoOrden.PENDIENTE)));     // la cola conserva el orden
        assertEquals(historialAntes, eventos(despues.historial(100)));        // la pila, con lo más reciente arriba
        assertEquals("ORDEN_CANCELADA#3", eventos(despues.historial(1)));
        assertEquals(carteraAntes, despues.estadoCartera(100));
        assertEquals("1", ids(despues.ordenes(EstadoOrden.EJECUTADA)));
        assertEquals("3", ids(despues.ordenes(EstadoOrden.CANCELADA)));
        assertEquals("segunda", despues.obtener(2).motivo());

        // La FIFO sigue funcionando y los ids continúan donde iban.
        assertEquals(2, despues.procesarSiguiente().orElseThrow().id());
        assertEquals(5, despues.crearCompra(50, null).id());
    }

    @Test
    void deshacerFuncionaDespuesDeRecargar() {
        LibroDeOrdenes antes = libroNuevo();
        antes.crearCompra(100, null);
        antes.crearCompra(200, null);
        LibroDeOrdenes despues = libroNuevo();
        assertEquals(2, despues.deshacerUltimaOrden().orElseThrow().id());
        assertEquals(1, despues.deshacerUltimaOrden().orElseThrow().id());
        assertTrue(despues.deshacerUltimaOrden().isEmpty());
    }

    @Test
    void cadaCambioQuedaGuardadoEnElMomento() throws IOException {
        LibroDeOrdenes libro = libroNuevo();
        libro.crearCompra(100, null);
        assertTrue(Files.readString(carpeta.resolve("ordenes.json")).contains("\"id\":1"));
        libro.procesarSiguiente();
        assertTrue(Files.readString(carpeta.resolve("cartera.json")).contains("\"saldoUsdt\":9900"));
    }

    @Test
    void conArchivoDanadoArrancaLimpioSinFallar() throws IOException {
        LibroDeOrdenes antes = libroNuevo();
        antes.crearCompra(100, null);
        Files.writeString(carpeta.resolve("cartera.json"), "{ esto no es json");

        LibroDeOrdenes despues = new LibroDeOrdenes(new Cartera(), fuente, "BTCUSDT");
        despues.usarAlmacen(new AlmacenArchivos(carpeta));
        assertEquals(0, despues.cantidadPendientes());
        assertEquals(10_000, despues.estadoCartera(100).saldoUsdt());
        assertEquals(1, despues.crearCompra(10, null).id());
        // Al seguir trabajando se vuelven a escribir archivos sanos.
        assertTrue(Files.readString(carpeta.resolve("cartera.json")).startsWith("{\"version\":1"));
    }

    @Test
    void sinNadaGuardadoEmpiezaLimpio() {
        LibroDeOrdenes libro = new LibroDeOrdenes(new Cartera(), fuente, "BTCUSDT");
        assertFalse(libro.usarAlmacen(new AlmacenArchivos(carpeta)));
        assertEquals(0, libro.historial(10).tamanio());
    }
}
