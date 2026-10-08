package com.bitcoinai.backend.estrategia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import org.junit.jupiter.api.Test;

class CombinadaYPronosticoTest {

    private static final ListaDoble<Vela> VELAS = Sinteticas.deCierres(100, 101, 102);

    private static EstrategiaCombinada combinar(Object... estrategiasYPesos) {
        Lista<EstrategiaCombinada.Componente> componentes = new Lista<>();
        for (int i = 0; i < estrategiasYPesos.length; i += 2) {
            componentes.agregar(new EstrategiaCombinada.Componente(
                    (Estrategia) estrategiasYPesos[i], ((Number) estrategiasYPesos[i + 1]).doubleValue()));
        }
        return new EstrategiaCombinada(componentes);
    }

    private static EstrategiaGuion fija(String nombre, Senal senal, double confianza) {
        return EstrategiaGuion.fija(nombre, senal, confianza);
    }

    // ---------- votación ponderada ----------

    @Test
    void ganaLaSenalConMayorPuntajePonderado() {
        // COMPRAR 0,8·1, VENDER 0,6·1, MANTENER 0,25·1 → puntajes /3: 0,267 / 0,2 / 0,083
        EstrategiaCombinada c = combinar(fija("a", Senal.COMPRAR, 0.8), 1, fija("b", Senal.VENDER, 0.6), 1,
                fija("c", Senal.MANTENER, 0), 1);
        Decision d = c.evaluar(VELAS);
        assertEquals(Senal.COMPRAR, d.senal());
        assertEquals(0.8 / 3, d.confianza(), 1e-12);
        assertEquals("Votación ponderada: COMPRAR 0.27, VENDER 0.20, MANTENER 0.08; gana COMPRAR.", d.motivo());
    }

    @Test
    void losPesosCambianElResultado() {
        // Con peso 0 para quien compra: VENDER 0,6/2 = 0,3 frente a MANTENER 0,25/2 = 0,125
        EstrategiaCombinada c = combinar(fija("a", Senal.COMPRAR, 0.8), 0, fija("b", Senal.VENDER, 0.6), 1,
                fija("c", Senal.MANTENER, 0), 1);
        Decision d = c.evaluar(VELAS);
        assertEquals(Senal.VENDER, d.senal());
        assertEquals(0.3, d.confianza(), 1e-12);
    }

    @Test
    void dosQueMantienenLeGananAUnaSenalDebil() {
        // COMPRAR 0,4 frente a MANTENER 0,25 + 0,25 = 0,5
        EstrategiaCombinada c = combinar(fija("a", Senal.COMPRAR, 0.4), 1, fija("b", Senal.MANTENER, 0), 1,
                fija("c", Senal.MANTENER, 0), 1);
        assertEquals(Senal.MANTENER, c.evaluar(VELAS).senal());
    }

    @Test
    void siComprarYVenderEmpatanSeMantiene() {
        EstrategiaCombinada c = combinar(fija("a", Senal.COMPRAR, 0.7), 1, fija("b", Senal.VENDER, 0.7), 1);
        Decision d = c.evaluar(VELAS);
        assertEquals(Senal.MANTENER, d.senal());
        assertTrue(d.motivo().contains("se contradicen"), d.motivo());
    }

    @Test
    void pesosInvalidos() {
        assertThrows(IllegalArgumentException.class, () -> combinar(fija("a", Senal.COMPRAR, 1), 0));
        assertThrows(IllegalArgumentException.class, () -> combinar(fija("a", Senal.COMPRAR, 1), -1));
        assertThrows(IllegalArgumentException.class, () -> new EstrategiaCombinada(new Lista<>()));
        assertThrows(IllegalArgumentException.class, () -> new EstrategiaCombinada(0, 0, 0));
    }

    @Test
    void parametrosMuestranPesosYEstrategias() {
        assertEquals("{pesos={cruce=2.0, rsi=1.0, macd=0.5}, estrategias={cruce={corta=20, larga=50}, "
                        + "rsi={periodo=14, sobreventa=30.0, sobrecompra=70.0}, macd={rapido=12, lento=26, senal=9}}}",
                new EstrategiaCombinada(2, 1, 0.5).parametros().toString());
    }

    // ---------- pronóstico ----------

    @Test
    void direccionSegunLaSenal() {
        assertEquals(Direccion.SUBE, Pronostico.direccionDe(Senal.COMPRAR));
        assertEquals(Direccion.BAJA, Pronostico.direccionDe(Senal.VENDER));
        assertEquals(Direccion.LATERAL, Pronostico.direccionDe(Senal.MANTENER));
    }

    @Test
    void pronosticoDeLaCombinadaSeJustificaConLasQueVotaronLoMismo() {
        EstrategiaCombinada c = combinar(fija("a", Senal.COMPRAR, 0.9), 1, fija("b", Senal.COMPRAR, 0.7), 1,
                fija("c", Senal.VENDER, 0.6), 1);
        Decision d = c.evaluar(VELAS);
        Pronostico p = Pronostico.desde(c, VELAS, d);
        assertEquals(Direccion.SUBE, p.direccion());
        assertEquals(d.confianza(), p.confianza());
        assertEquals("[a: a dice COMPRAR en la vela 2., b: b dice COMPRAR en la vela 2.]", Sinteticas.texto(p.justificacion()));
        assertEquals("{a=1.0, b=1.0, c=1.0}", p.indicadores().toString());
        assertEquals("Resultado de pruebas con datos históricos; no es asesoría financiera ni garantiza ganancias",
                p.aviso());
    }

    @Test
    void pronosticoRealTrasUnGiroAlcista() {
        // En la vela 63 el RSI sale de sobreventa: la combinada compra.
        ListaDoble<Vela> velas = new ListaDoble<>();
        int i = 0;
        for (Vela v : Sinteticas.alcistaTrasCaida()) {
            if (i++ > 63) {
                break;
            }
            velas.agregarFinal(v);
        }
        EstrategiaCombinada combinada = new EstrategiaCombinada();
        Decision d = combinada.evaluar(velas);
        Pronostico p = Pronostico.desde(combinada, velas, d);
        assertEquals(Direccion.SUBE, p.direccion());
        assertTrue(p.justificacion().primero().startsWith("rsi: El RSI salió de sobreventa"), p.justificacion().primero());
        assertTrue(p.indicadores().containsKey("rsi") && p.indicadores().containsKey("smaLarga"));
    }

    @Test
    void pronosticoDeUnaEstrategiaSimpleUsaSuMotivo() {
        EstrategiaRsi rsi = new EstrategiaRsi();
        ListaDoble<Vela> velas = Sinteticas.lateralPlano();
        Decision d = rsi.evaluar(velas);
        Pronostico p = Pronostico.desde(rsi, velas, d);
        assertEquals(Direccion.LATERAL, p.direccion());
        assertEquals(d.motivo(), p.justificacion().primero());
        assertEquals(50.0, p.indicadores().get("rsi"));
    }

    // ---------- decisión ----------

    @Test
    void decisionValidaConfianzaYMotivo() {
        assertThrows(IllegalArgumentException.class, () -> new Decision(0, Senal.COMPRAR, 1, 1.5, "x"));
        assertThrows(IllegalArgumentException.class, () -> new Decision(0, Senal.COMPRAR, 1, -0.1, "x"));
        assertThrows(IllegalArgumentException.class, () -> new Decision(0, Senal.COMPRAR, 1, Double.NaN, "x"));
        assertThrows(IllegalArgumentException.class, () -> new Decision(0, Senal.COMPRAR, 1, 0.5, " "));
        assertThrows(NullPointerException.class, () -> new Decision(0, null, 1, 0.5, "x"));
    }
}
