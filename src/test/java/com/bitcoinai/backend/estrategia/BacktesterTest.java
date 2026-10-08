package com.bitcoinai.backend.estrategia;

import static com.bitcoinai.backend.estrategia.Sinteticas.DIA;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.indicadores.PuntoIndicador;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Iterator;
import org.junit.jupiter.api.Test;

class BacktesterTest {

    /** Aperturas 100, 110, 120, 130, 140 y cierres 5 más arriba. */
    private static ListaDoble<Vela> cincoVelas() {
        return Sinteticas.velas(new double[] {100, 110, 120, 130, 140}, new double[] {105, 115, 125, 135, 145});
    }

    // ---------- comisión y ejecución ----------

    @Test
    void comisionSeDescuentaEnLaCompraYEnLaVenta() {
        // Señal de compra en la vela 0 → se compra en la apertura de la vela 1 (110).
        // Señal de venta en la vela 2 → se vende en la apertura de la vela 3 (130).
        EstrategiaGuion guion = EstrategiaGuion.conGuion().en(0, Senal.COMPRAR).en(2, Senal.VENDER);
        ResultadoBacktest r = new Backtester(1000, 0.001).ejecutar(guion, cincoVelas());

        double comisionCompra = 1000 * 0.001;                 // 1 USDT
        double btc = (1000 - comisionCompra) / 110;           // 999 / 110
        double bruto = btc * 130;
        double comisionVenta = bruto * 0.001;
        double capitalFinal = bruto - comisionVenta;

        assertEquals(capitalFinal, r.capitalFinal(), 1e-9);
        assertEquals(comisionCompra + comisionVenta, r.comisionesPagadas(), 1e-9);
        assertEquals(capitalFinal / 1000 - 1, r.rentabilidadTotal(), 1e-12);
        assertEquals(1, r.numeroOperaciones());

        OperacionCerrada op = r.operaciones().primero();
        assertEquals(DIA, op.tiempoEntrada());
        assertEquals(110, op.precioEntrada());
        assertEquals(3 * DIA, op.tiempoSalida());
        assertEquals(130, op.precioSalida());
        assertEquals(btc, op.cantidadBtc(), 1e-12);
        assertEquals(comisionCompra + comisionVenta, op.comisiones(), 1e-9);
        assertEquals(capitalFinal - 1000, op.ganancia(), 1e-9);
        assertEquals(op.ganancia() / 1000, op.rentabilidad(), 1e-12);
        assertEquals("guion dice VENDER en la vela 2.", op.motivoSalida());
    }

    @Test
    void sinComisionLaGananciaEsElCambioDePrecio() {
        EstrategiaGuion guion = EstrategiaGuion.conGuion().en(0, Senal.COMPRAR).en(2, Senal.VENDER);
        ResultadoBacktest r = new Backtester(1000, 0).ejecutar(guion, cincoVelas());
        assertEquals(1000.0 * 130 / 110, r.capitalFinal(), 1e-9);
        assertEquals(0, r.comisionesPagadas());
    }

    @Test
    void comprarYMantenerVaDeLaPrimeraAperturaAlUltimoCierreConComisiones() {
        ResultadoBacktest r = new Backtester(1000, 0.001).ejecutar(EstrategiaGuion.conGuion(), cincoVelas());
        assertEquals(0.999 * 0.999 * 145 / 100 - 1, r.rentabilidadComprarYMantener(), 1e-12);
        // la estrategia no operó: conserva el capital
        assertEquals(1000, r.capitalFinal());
        assertEquals(0, r.rentabilidadTotal());
        assertEquals(0, r.numeroOperaciones());
        assertEquals(0, r.tasaGanadoras());
        assertNull(r.factorBeneficio());
    }

    @Test
    void posicionAbiertaAlFinalSeCierraAlUltimoCierre() {
        ResultadoBacktest r = new Backtester(1000, 0).ejecutar(EstrategiaGuion.conGuion().en(0, Senal.COMPRAR), cincoVelas());
        OperacionCerrada op = r.operaciones().primero();
        assertEquals(145, op.precioSalida());
        assertEquals(4 * DIA, op.tiempoSalida());
        assertEquals("Cierre forzado al final del periodo.", op.motivoSalida());
        assertEquals(1000.0 * 145 / 110, r.capitalFinal(), 1e-9);
    }

    @Test
    void senalEnLaUltimaVelaNoLlegaAEjecutarse() {
        ResultadoBacktest r = new Backtester().ejecutar(EstrategiaGuion.conGuion().en(4, Senal.COMPRAR), cincoVelas());
        assertEquals(0, r.numeroOperaciones());
        assertEquals(1000, r.capitalFinal());
    }

    @Test
    void soloPosicionesLargas() {
        // VENDER sin posición se ignora; COMPRAR con posición también.
        EstrategiaGuion guion = EstrategiaGuion.conGuion()
                .en(0, Senal.VENDER).en(1, Senal.COMPRAR).en(2, Senal.COMPRAR).en(3, Senal.VENDER);
        ResultadoBacktest r = new Backtester(1000, 0).ejecutar(guion, cincoVelas());
        assertEquals(1, r.numeroOperaciones());
        assertEquals(120, r.operaciones().primero().precioEntrada());
        assertEquals(140, r.operaciones().primero().precioSalida());
    }

    // ---------- métricas ----------

    @Test
    void metricasConUnaOperacionGanadoraYUnaPerdedora() {
        // op 1: compra a 100 (vela 1), vende a 120 (vela 3) → 1000 → 1200 (+200)
        // op 2: compra a 120 (vela 4), vende a 90 (vela 6)  → 1200 → 900  (−300)
        double[] precios = {100, 100, 120, 120, 120, 90, 90};
        EstrategiaGuion guion = EstrategiaGuion.conGuion()
                .en(0, Senal.COMPRAR).en(2, Senal.VENDER).en(3, Senal.COMPRAR).en(5, Senal.VENDER);
        ResultadoBacktest r = new Backtester(1000, 0).ejecutar(guion, Sinteticas.velas(precios, precios));

        assertEquals(900, r.capitalFinal(), 1e-9);
        assertEquals(-0.1, r.rentabilidadTotal(), 1e-12);
        assertEquals(2, r.numeroOperaciones());
        assertEquals(0.5, r.tasaGanadoras());
        assertEquals(200.0 / 300.0, r.factorBeneficio(), 1e-12);
        assertEquals(0.25, r.caidaMaxima(), 1e-12); // la curva baja de 1200 a 900
        assertEquals(7, r.velasAnalizadas());
        assertEquals(7, r.numeroDecisiones());
        assertEquals(0, r.tiempoInicio());
        assertEquals(7 * DIA - 1, r.tiempoFin());
    }

    @Test
    void decisionesRecientesSalenDeLaPilaDeLaMasNuevaALaMasVieja() {
        double[] precios = {100, 100, 120, 120, 120, 90, 90};
        EstrategiaGuion guion = EstrategiaGuion.conGuion()
                .en(0, Senal.COMPRAR).en(2, Senal.VENDER).en(3, Senal.COMPRAR).en(5, Senal.VENDER);
        ResultadoBacktest r = new Backtester(1000, 0).ejecutar(guion, Sinteticas.velas(precios, precios));
        StringBuilder orden = new StringBuilder();
        for (Decision d : r.decisionesRecientes()) {
            orden.append(d.senal()).append('@').append(d.tiempo() / DIA).append(' ');
        }
        assertEquals("VENDER@5 COMPRAR@3 VENDER@2 COMPRAR@0 ", orden.toString());
    }

    @Test
    void curvaDeCapitalValoraLaPosicionAlCierreDeCadaVela() {
        EstrategiaGuion guion = EstrategiaGuion.conGuion().en(0, Senal.COMPRAR).en(2, Senal.VENDER);
        ResultadoBacktest r = new Backtester(1000, 0).ejecutar(guion, cincoVelas());
        double btc = 1000.0 / 110;
        double[] esperado = {1000, btc * 115, btc * 125, btc * 130, btc * 130};
        int i = 0;
        for (PuntoIndicador p : r.curvaCapital()) {
            assertEquals(i * DIA, p.tiempo());
            assertEquals(esperado[i], p.valor(), 1e-9, "punto " + i);
            i++;
        }
        assertEquals(5, i);
    }

    // ---------- sin mirar el futuro ----------

    @Test
    void laEstrategiaSoloRecibeLasVelasHastaLaActual() {
        EstrategiaGuion espia = EstrategiaGuion.conGuion();
        new Backtester().ejecutar(espia, Sinteticas.alcistaTrasCaida());
        int llamada = 0;
        Iterator<Long> tiempos = espia.tiemposVistos.iterator();
        for (int tamanio : espia.tamaniosVistos) {
            assertEquals(llamada + 1, tamanio, "en la vela " + llamada + " debía ver " + (llamada + 1) + " velas");
            assertEquals(llamada * DIA, tiempos.next(), "la última vela vista debe ser la actual");
            llamada++;
        }
        assertEquals(120, llamada);
    }

    @Test
    void elResultadoHastaLaVelaTNoCambiaAlAgregarVelasPosteriores() {
        ListaDoble<Vela> todas = Sinteticas.alcistaTrasCaida();
        ListaDoble<Vela> hasta80 = new ListaDoble<>();
        for (Vela v : todas) {
            if (hasta80.tamanio() == 80) {
                break;
            }
            hasta80.agregarFinal(v);
        }
        Backtester backtester = new Backtester(1000, 0.001);
        ResultadoBacktest corto = backtester.ejecutar(new EstrategiaCombinada(), hasta80);
        ResultadoBacktest largo = backtester.ejecutar(new EstrategiaCombinada(), todas);

        Iterator<PuntoIndicador> itLargo = largo.curvaCapital().iterator();
        int i = 0;
        for (PuntoIndicador p : corto.curvaCapital()) {
            PuntoIndicador q = itLargo.next();
            assertEquals(p.tiempo(), q.tiempo());
            assertEquals(p.valor(), q.valor(), 0.0, "la curva difiere en la vela " + i);
            i++;
        }
        assertEquals(80, i);
        // La primera compra es la misma en los dos casos.
        assertEquals(corto.operaciones().primero().tiempoEntrada(), largo.operaciones().primero().tiempoEntrada());
        assertEquals(corto.operaciones().primero().precioEntrada(), largo.operaciones().primero().precioEntrada());
    }

    // ---------- periodo parcial y bordes ----------

    @Test
    void inicioOperacionesUsaLoAnteriorSoloComoHistorial() {
        EstrategiaGuion espia = EstrategiaGuion.conGuion();
        ResultadoBacktest r = new Backtester().ejecutar(espia, cincoVelas(), 2);
        assertEquals(3, espia.tamaniosVistos.primero()); // ya ve las velas 0 y 1 como historial
        assertEquals(3, espia.tamaniosVistos.tamanio());  // pero solo decide en las velas 2, 3 y 4
        assertEquals(3, r.velasAnalizadas());
        assertEquals(2 * DIA, r.tiempoInicio());
        assertEquals(0.999 * 0.999 * 145 / 120 - 1, r.rentabilidadComprarYMantener(), 1e-12);
    }

    @Test
    void sinVelasNoHayOperaciones() {
        ResultadoBacktest r = new Backtester(500, 0.001).ejecutar(new CruceDeMedias(), new ListaDoble<>());
        assertEquals(500, r.capitalFinal());
        assertEquals(0, r.rentabilidadComprarYMantener());
        assertEquals(0, r.velasAnalizadas());
        assertEquals(0, r.caidaMaxima());
    }

    @Test
    void parametrosInvalidos() {
        assertThrows(IllegalArgumentException.class, () -> new Backtester(0, 0.001));
        assertThrows(IllegalArgumentException.class, () -> new Backtester(1000, -0.1));
        assertThrows(IllegalArgumentException.class, () -> new Backtester(1000, 1));
        assertThrows(IllegalArgumentException.class, () -> new Backtester().ejecutar(new CruceDeMedias(), cincoVelas(), 6));
    }
}
