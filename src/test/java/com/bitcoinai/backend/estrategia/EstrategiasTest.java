package com.bitcoinai.backend.estrategia;

import static com.bitcoinai.backend.estrategia.Sinteticas.GIRO;
import static com.bitcoinai.backend.estrategia.Sinteticas.alcistaTrasCaida;
import static com.bitcoinai.backend.estrategia.Sinteticas.bajistaTrasSubida;
import static com.bitcoinai.backend.estrategia.Sinteticas.indiceDe;
import static com.bitcoinai.backend.estrategia.Sinteticas.lateralPlano;
import static com.bitcoinai.backend.estrategia.Sinteticas.lateralZigzag;
import static com.bitcoinai.backend.estrategia.Sinteticas.senales;
import static com.bitcoinai.backend.estrategia.Sinteticas.texto;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import org.junit.jupiter.api.Test;

/**
 * Señales esperadas de cada estrategia en tendencias sintéticas: alcista tras una
 * caída (debe comprar después del giro), bajista tras una subida (debe vender) y
 * lateral (no debe hacer nada).
 */
class EstrategiasTest {

    /** Exactamente una señal, del tipo esperado, después del giro. */
    private static void assertUnaSenalTrasElGiro(Estrategia estrategia, ListaDoble<Vela> velas, Senal esperada) {
        Lista<String> senales = senales(estrategia, velas);
        assertEquals(1, senales.tamanio(), "señales: " + texto(senales));
        assertTrue(senales.primero().startsWith(esperada.name()), "señales: " + texto(senales));
        assertTrue(indiceDe(senales.primero()) > GIRO, "la señal debe llegar después del giro: " + texto(senales));
    }

    private static void assertSinSenales(Estrategia estrategia, ListaDoble<Vela> velas) {
        Lista<String> senales = senales(estrategia, velas);
        assertTrue(senales.estaVacia(), "no debía haber señales: " + texto(senales));
    }

    // ---------- Cruce de medias ----------

    @Test
    void cruceCompraEnTendenciaAlcistaYVendeEnBajista() {
        assertUnaSenalTrasElGiro(new CruceDeMedias(5, 10), alcistaTrasCaida(), Senal.COMPRAR);
        assertUnaSenalTrasElGiro(new CruceDeMedias(5, 10), bajistaTrasSubida(), Senal.VENDER);
        assertUnaSenalTrasElGiro(new CruceDeMedias(), alcistaTrasCaida(), Senal.COMPRAR);
    }

    @Test
    void cruceNoHaceNadaEnLateralPlano() {
        assertSinSenales(new CruceDeMedias(5, 10), lateralPlano());
    }

    @Test
    void cruceExplicaElMotivoConLasMedias() {
        ListaDoble<Vela> velas = Sinteticas.deCierres(10, 10, 10, 10, 10, 20);
        Decision decision = new CruceDeMedias(2, 4).evaluar(velas);
        assertEquals(Senal.COMPRAR, decision.senal());
        assertTrue(decision.motivo().startsWith("Cruce alcista: la SMA 2 (15.00) cruzó por encima de la SMA 4 (12.50)"),
                decision.motivo());
        assertEquals(1.0, decision.confianza()); // separación del 12,5 % → confianza máxima
        assertEquals(5 * Sinteticas.DIA, decision.tiempo());
        assertEquals(20, decision.precio());
    }

    // ---------- RSI ----------

    @Test
    void rsiCompraAlSalirDeSobreventaYVendeAlSalirDeSobrecompra() {
        assertUnaSenalTrasElGiro(new EstrategiaRsi(), alcistaTrasCaida(), Senal.COMPRAR);
        assertUnaSenalTrasElGiro(new EstrategiaRsi(), bajistaTrasSubida(), Senal.VENDER);
    }

    @Test
    void rsiCompraEnLaVelaExactaCalculadaAMano() {
        // Tras 45 velas con RSI 0, las subidas llevan el RSI a ~10, ~19, ~27 y ~34:
        // cruza 30 en la cuarta vela de subida (índice 63).
        Lista<String> senales = senales(new EstrategiaRsi(), alcistaTrasCaida());
        assertEquals("COMPRAR@63", senales.primero());
    }

    @Test
    void rsiNoHaceNadaEnLateral() {
        assertSinSenales(new EstrategiaRsi(), lateralPlano());
        assertSinSenales(new EstrategiaRsi(), lateralZigzag());
    }

    // ---------- MACD ----------

    @Test
    void macdCompraTrasElGiroAlcistaYVendeTrasElBajista() {
        assertUnaSenalTrasElGiro(new EstrategiaMacd(), alcistaTrasCaida(), Senal.COMPRAR);
        assertUnaSenalTrasElGiro(new EstrategiaMacd(), bajistaTrasSubida(), Senal.VENDER);
    }

    @Test
    void macdNoHaceNadaEnLateralPlano() {
        assertSinSenales(new EstrategiaMacd(), lateralPlano());
    }

    // ---------- Combinada ----------

    @Test
    void combinadaCompraEnAlcistaSinVenderYVendeEnBajistaSinComprar() {
        Lista<String> alcista = senales(new EstrategiaCombinada(), alcistaTrasCaida());
        assertTrue(!alcista.estaVacia() && texto(alcista).indexOf("VENDER") < 0, texto(alcista));
        for (String s : alcista) {
            assertTrue(indiceDe(s) > GIRO, texto(alcista));
        }
        Lista<String> bajista = senales(new EstrategiaCombinada(), bajistaTrasSubida());
        assertTrue(!bajista.estaVacia() && texto(bajista).indexOf("COMPRAR") < 0, texto(bajista));
    }

    @Test
    void combinadaNoHaceNadaEnLateralPlano() {
        assertSinSenales(new EstrategiaCombinada(), lateralPlano());
    }

    // ---------- Casos generales ----------

    @Test
    void conPocasVelasTodasMantienenConConfianzaCero() {
        ListaDoble<Vela> pocas = Sinteticas.deCierres(1, 2, 3);
        for (Estrategia e : new Estrategia[] {new CruceDeMedias(), new EstrategiaRsi(), new EstrategiaMacd(),
                new EstrategiaCombinada()}) {
            Decision d = e.evaluar(pocas);
            assertEquals(Senal.MANTENER, d.senal(), e.nombre());
            assertEquals(0.0, d.confianza(), e.nombre());
            assertTrue(d.motivo().startsWith("Faltan velas"), d.motivo());
        }
        assertEquals(Senal.MANTENER, new CruceDeMedias().evaluar(new ListaDoble<>()).senal());
        assertEquals(Senal.MANTENER, new EstrategiaCombinada().evaluar(null).senal());
    }

    @Test
    void velasMinimasDeCadaEstrategia() {
        assertEquals(51, new CruceDeMedias().velasMinimas());
        assertEquals(16, new EstrategiaRsi().velasMinimas());
        assertEquals(35, new EstrategiaMacd().velasMinimas());
        assertEquals(51, new EstrategiaCombinada().velasMinimas());
    }

    @Test
    void evaluarNoModificaLasVelas() {
        ListaDoble<Vela> velas = alcistaTrasCaida();
        new EstrategiaCombinada().evaluar(velas);
        assertEquals(120, velas.tamanio());
    }

    @Test
    void indicadoresActualesDeCadaEstrategia() {
        ListaDoble<Vela> velas = alcistaTrasCaida();
        assertEquals("[smaCorta, smaLarga]", new CruceDeMedias().indicadoresActuales(velas).keySet().toString());
        assertEquals("[rsi]", new EstrategiaRsi().indicadoresActuales(velas).keySet().toString());
        assertEquals("[macd, senalMacd, histogramaMacd]",
                new EstrategiaMacd().indicadoresActuales(velas).keySet().toString());
        assertEquals(6, new EstrategiaCombinada().indicadoresActuales(velas).size());
        assertTrue(new CruceDeMedias().indicadoresActuales(Sinteticas.deCierres(1)).isEmpty());
    }

    @Test
    void parametrosInvalidosEnLosConstructores() {
        assertThrows(IllegalArgumentException.class, () -> new CruceDeMedias(50, 20));
        assertThrows(IllegalArgumentException.class, () -> new CruceDeMedias(0, 20));
        assertThrows(IllegalArgumentException.class, () -> new EstrategiaRsi(14, 60, 70));
        assertThrows(IllegalArgumentException.class, () -> new EstrategiaRsi(0, 30, 70));
        assertThrows(IllegalArgumentException.class, () -> new EstrategiaMacd(26, 12, 9));
    }
}
