package com.bitcoinai.backend.persistencia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.simulacion.DatosCartera;
import com.bitcoinai.backend.simulacion.EstadoOrden;
import com.bitcoinai.backend.simulacion.EstadoSimulacion;
import com.bitcoinai.backend.simulacion.Evento;
import com.bitcoinai.backend.simulacion.Orden;
import com.bitcoinai.backend.simulacion.TipoEvento;
import com.bitcoinai.backend.simulacion.TipoOrden;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class AlmacenArchivosTest {

    @TempDir
    Path carpeta;

    @SafeVarargs
    private static <T> Lista<T> listaDe(T... elementos) {
        Lista<T> lista = new Lista<>();
        for (T e : elementos) {
            lista.agregar(e);
        }
        return lista;
    }

    private static EstadoSimulacion estadoDeEjemplo() {
        Orden p1 = new Orden(3, TipoOrden.COMPRA, 100.0, false, EstadoOrden.PENDIENTE, 1000, null, null, null, null, "manual", null);
        Orden p2 = new Orden(4, TipoOrden.VENTA, null, true, EstadoOrden.PENDIENTE, 1001, null, null, null, null, "stop-loss: x", null);
        Orden r1 = new Orden(1, TipoOrden.COMPRA, 500.0, false, EstadoOrden.EJECUTADA, 900, 950L, 83000.5, 0.006, 0.5,
                "manual", "Compró \"bien\"\nlínea 2");
        Orden r2 = new Orden(2, TipoOrden.COMPRA, 99999.0, false, EstadoOrden.RECHAZADA, 960, 970L, 83000.0, null, null,
                "manual", "Saldo insuficiente");
        Evento e1 = new Evento(900, TipoEvento.ORDEN_CREADA, 1L, "Orden #1 creada");
        Evento e2 = new Evento(950, TipoEvento.DECISION_BOT, null, "El bot decidió MANTENER");
        return new EstadoSimulacion(new DatosCartera(10_000, 9_500, 0.006, 500, 12.5, 0.5), 5,
                listaDe(p1, p2), listaDe(r1, r2), listaDe(1L, 2L, 3L, 4L), listaDe(e1, e2));
    }

    @Test
    void sinArchivosNoHayNadaQueCargar() {
        assertTrue(new AlmacenArchivos(carpeta.resolve("no-existe")).cargar().isEmpty());
    }

    @Test
    void idaYVueltaConservaTodoYElOrden() {
        AlmacenArchivos almacen = new AlmacenArchivos(carpeta);
        EstadoSimulacion original = estadoDeEjemplo();
        almacen.guardar(original);
        EstadoSimulacion cargado = almacen.cargar().orElseThrow();

        assertEquals(original.cartera(), cargado.cartera());
        assertEquals(5, cargado.siguienteId());
        assertEquals(original.pendientes().obtener(0), cargado.pendientes().obtener(0));
        assertEquals(original.pendientes().obtener(1), cargado.pendientes().obtener(1)); // monto null y todo true
        assertEquals(original.registro().obtener(0), cargado.registro().obtener(0));     // texto con comillas y salto
        assertEquals(original.registro().obtener(1), cargado.registro().obtener(1));
        assertEquals("[1, 2, 3, 4]", texto(cargado.creadas()));
        assertEquals(original.eventos().obtener(0), cargado.eventos().obtener(0));
        assertNull(cargado.eventos().obtener(1).idOrden());
    }

    @Test
    void escribeLosTresArchivosSinDejarTemporales() throws IOException {
        new AlmacenArchivos(carpeta).guardar(estadoDeEjemplo());
        assertTrue(Files.exists(carpeta.resolve("cartera.json")));
        assertTrue(Files.exists(carpeta.resolve("ordenes.json")));
        assertTrue(Files.exists(carpeta.resolve("historial.json")));
        try (Stream<Path> archivos = Files.list(carpeta)) {
            assertFalse(archivos.anyMatch(p -> p.toString().endsWith(".tmp")), "quedó un archivo temporal");
        }
        String ordenes = Files.readString(carpeta.resolve("ordenes.json"));
        assertTrue(ordenes.startsWith("{\"version\":1,\"siguienteId\":5,\"pendientes\":[{\"id\":3,"), ordenes);
    }

    @Test
    void guardarDosVecesReemplazaElArchivo() {
        AlmacenArchivos almacen = new AlmacenArchivos(carpeta);
        almacen.guardar(estadoDeEjemplo());
        EstadoSimulacion vacio = new EstadoSimulacion(new DatosCartera(10_000, 10_000, 0, 0, 0, 0), 1,
                new Lista<>(), new Lista<>(), new Lista<>(), new Lista<>());
        almacen.guardar(vacio);
        EstadoSimulacion cargado = almacen.cargar().orElseThrow();
        assertEquals(10_000, cargado.cartera().saldoUsdt());
        assertTrue(cargado.pendientes().estaVacia());
    }

    @Test
    void ordenesDanadasDanEstadoLimpioYSeApartan() throws IOException {
        AlmacenArchivos almacen = new AlmacenArchivos(carpeta);
        almacen.guardar(estadoDeEjemplo());
        Files.writeString(carpeta.resolve("ordenes.json"), "{\"version\":1,\"pendientes\":[", StandardCharsets.UTF_8);

        Optional<EstadoSimulacion> cargado = almacen.cargar();
        // La cartera no se usa sin sus órdenes, pero el historial (sano) sí se conserva.
        assertTrue(cargado.isPresent());
        assertNull(cargado.get().cartera());
        assertTrue(cargado.get().pendientes().estaVacia());
        assertEquals(2, cargado.get().eventos().tamanio());
        assertFalse(Files.exists(carpeta.resolve("ordenes.json")));
        assertFalse(Files.exists(carpeta.resolve("cartera.json")));
        try (Stream<Path> archivos = Files.list(carpeta)) {
            assertEquals(2, archivos.filter(p -> p.getFileName().toString().contains(".danado-")).count());
        }
    }

    @Test
    void todosDanadosEsComoNoTenerNada() throws IOException {
        Files.writeString(carpeta.resolve("cartera.json"), "no es json");
        Files.writeString(carpeta.resolve("ordenes.json"), "{\"version\":1}");
        Files.writeString(carpeta.resolve("historial.json"), "[]");
        assertTrue(new AlmacenArchivos(carpeta).cargar().isEmpty());
    }

    @Test
    void datosConValoresImposiblesSeTratanComoDanados() throws IOException {
        AlmacenArchivos almacen = new AlmacenArchivos(carpeta);
        almacen.guardar(estadoDeEjemplo());
        String cartera = Files.readString(carpeta.resolve("cartera.json")).replace("\"btc\":0.006", "\"btc\":-1");
        Files.writeString(carpeta.resolve("cartera.json"), cartera);
        assertNull(almacen.cargar().orElseThrow().cartera());
    }

    @Test
    void siFaltaUnoDeLosDosArchivosPrincipalesNoSeUsaElOtro() throws IOException {
        AlmacenArchivos almacen = new AlmacenArchivos(carpeta);
        almacen.guardar(estadoDeEjemplo());
        Files.delete(carpeta.resolve("ordenes.json"));
        Files.delete(carpeta.resolve("historial.json"));
        assertTrue(almacen.cargar().isEmpty());
    }

    @Test
    void versionDesconocidaSeRechaza() throws IOException {
        AlmacenArchivos almacen = new AlmacenArchivos(carpeta);
        almacen.guardar(estadoDeEjemplo());
        Files.writeString(carpeta.resolve("historial.json"), "{\"version\":99,\"eventos\":[]}");
        assertTrue(almacen.cargar().orElseThrow().eventos().estaVacia());
    }

    private static String texto(Lista<?> lista) {
        StringBuilder sb = new StringBuilder("[");
        for (Object o : lista) {
            if (sb.length() > 1) {
                sb.append(", ");
            }
            sb.append(o);
        }
        return sb.append(']').toString();
    }
}
