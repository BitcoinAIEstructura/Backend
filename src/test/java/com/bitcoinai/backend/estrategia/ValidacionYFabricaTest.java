package com.bitcoinai.backend.estrategia;

import static com.bitcoinai.backend.estrategia.Sinteticas.DIA;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.mercado.FuenteFalsa;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Map;
import org.junit.jupiter.api.Test;

class ValidacionYFabricaTest {

    // ---------- validación entrenamiento / prueba ----------

    @Test
    void divisionSetentaTreintaNoMezclaDatos() {
        ListaDoble<Vela> velas = FuenteFalsa.generarVelas(100, Intervalo.D1); // siempre sube
        long inicio = velas.primero().tiempoApertura();
        long tiempoUltimaDeEntrenamiento = inicio + 69 * DIA;

        EstrategiaGuion comprador = EstrategiaGuion.fija("comprador", Senal.COMPRAR, 1);
        EstrategiaGuion quieto = EstrategiaGuion.fija("quieto", Senal.MANTENER, 0);
        Lista<Estrategia> candidatos = new Lista<>();
        candidatos.agregar(quieto);
        candidatos.agregar(comprador);

        ResultadoValidacion r = new ValidacionEntrenamientoPrueba(new Backtester(), 0.7).ejecutar(candidatos, velas);

        assertEquals(70, r.velasEntrenamiento());
        assertEquals(30, r.velasPrueba());
        // El candidato descartado solo vio velas de entrenamiento.
        for (long t : quieto.tiemposVistos) {
            assertTrue(t <= tiempoUltimaDeEntrenamiento, "el descartado vio una vela de prueba");
        }
        // El elegido: sus primeras 70 llamadas (entrenamiento) tampoco vieron velas de prueba.
        int llamada = 0;
        for (long t : comprador.tiemposVistos) {
            if (llamada++ < 70) {
                assertTrue(t <= tiempoUltimaDeEntrenamiento, "el entrenamiento vio una vela de prueba");
            }
        }
        // Los dos tramos no se solapan.
        assertTrue(r.entrenamiento().tiempoFin() < r.prueba().tiempoInicio());
        assertEquals(inicio + 70 * DIA, r.prueba().tiempoInicio());
        assertEquals(70, r.entrenamiento().velasAnalizadas());
        assertEquals(30, r.prueba().velasAnalizadas());
    }

    @Test
    void eligeElMejorCandidatoSegunElEntrenamientoYLoMideEnPrueba() {
        ListaDoble<Vela> velas = FuenteFalsa.generarVelas(100, Intervalo.D1);
        Lista<Estrategia> candidatos = new Lista<>();
        candidatos.agregar(EstrategiaGuion.fija("quieto", Senal.MANTENER, 0));
        candidatos.agregar(EstrategiaGuion.fija("comprador", Senal.COMPRAR, 1));

        ResultadoValidacion r = new ValidacionEntrenamientoPrueba(new Backtester(), 0.7).ejecutar(candidatos, velas);

        assertEquals("comprador", r.estrategia());
        assertEquals("{nombre=comprador}", r.parametrosElegidos().toString());
        assertEquals(2, r.candidatos().tamanio());
        assertEquals(0, r.candidatos().primero().rentabilidad());
        assertTrue(r.candidatos().ultimo().rentabilidad() > 0);
        assertTrue(r.prueba().rentabilidadTotal() > 0);
        assertEquals(1, r.prueba().numeroOperaciones());
    }

    @Test
    void enPruebaLasVelasDeEntrenamientoSoloSirvenDeHistorial() {
        ListaDoble<Vela> velas = FuenteFalsa.generarVelas(10, Intervalo.D1);
        EstrategiaGuion unico = EstrategiaGuion.fija("unico", Senal.MANTENER, 0);
        Lista<Estrategia> candidatos = new Lista<>();
        candidatos.agregar(unico);
        new ValidacionEntrenamientoPrueba(new Backtester(), 0.7).ejecutar(candidatos, velas);
        // 7 llamadas de entrenamiento (tamaños 1..7) y 3 de prueba (tamaños 8..10)
        assertEquals(10, unico.tamaniosVistos.tamanio());
        assertEquals(7, unico.tamaniosVistos.obtener(6));
        assertEquals(8, unico.tamaniosVistos.obtener(7));
    }

    @Test
    void validacionConEstrategiaRealDevuelveTodosLosCandidatos() {
        ResultadoValidacion r = new ValidacionEntrenamientoPrueba(new Backtester(), 0.7)
                .ejecutar(FabricaEstrategias.candidatos("cruce"), Sinteticas.alcistaTrasCaida());
        assertEquals(9, r.candidatos().tamanio());
        assertEquals(84, r.velasEntrenamiento());
        assertEquals(36, r.velasPrueba());
    }

    @Test
    void validacionParametrosInvalidos() {
        assertThrows(IllegalArgumentException.class, () -> new ValidacionEntrenamientoPrueba(new Backtester(), 1));
        assertThrows(IllegalArgumentException.class, () -> new ValidacionEntrenamientoPrueba(new Backtester(), 0));
        assertThrows(IllegalArgumentException.class, () -> new ValidacionEntrenamientoPrueba(new Backtester(), 0.7)
                .ejecutar(new Lista<>(), Sinteticas.lateralPlano()));
    }

    // ---------- fábrica ----------

    @Test
    void fabricaCreaCadaEstrategiaConSusValoresPorDefecto() {
        assertEquals("{corta=20, larga=50}",
                assertInstanceOf(CruceDeMedias.class, FabricaEstrategias.crear("cruce")).parametros().toString());
        assertEquals("{periodo=14, sobreventa=30.0, sobrecompra=70.0}",
                assertInstanceOf(EstrategiaRsi.class, FabricaEstrategias.crear("RSI")).parametros().toString());
        assertEquals("{rapido=12, lento=26, senal=9}",
                assertInstanceOf(EstrategiaMacd.class, FabricaEstrategias.crear("macd")).parametros().toString());
        assertInstanceOf(EstrategiaCombinada.class, FabricaEstrategias.crear("combinada"));
    }

    @Test
    void fabricaUsaLosParametrosRecibidos() {
        assertEquals("{corta=10, larga=30}",
                FabricaEstrategias.crear("cruce", Map.of("corta", "10", "larga", "30")).parametros().toString());
        Estrategia combinada = FabricaEstrategias.crear("combinada", Map.of("pesoRsi", "0", "corta", "5", "larga", "15"));
        assertEquals("{cruce=1.0, rsi=0.0, macd=1.0}", combinada.parametros().get("pesos").toString());
        assertTrue(combinada.parametros().get("estrategias").toString().contains("cruce={corta=5, larga=15}"));
    }

    @Test
    void fabricaRechazaNombresYParametrosInvalidos() {
        assertThrows(IllegalArgumentException.class, () -> FabricaEstrategias.crear("magia"));
        assertThrows(IllegalArgumentException.class, () -> FabricaEstrategias.crear(null));
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> FabricaEstrategias.crear("cruce", Map.of("corta", "50", "larga", "20")));
        assertEquals("Parámetro 'larga' (20) debe ser mayor que 'corta' (50)", e.getMessage());
        assertThrows(IllegalArgumentException.class, () -> FabricaEstrategias.crear("rsi", Map.of("sobreventa", "60")));
        assertThrows(IllegalArgumentException.class, () -> FabricaEstrategias.crear("macd", Map.of("senal", "x")));
        IllegalArgumentException pesos = assertThrows(IllegalArgumentException.class, () -> FabricaEstrategias
                .crear("combinada", Map.of("pesoCruce", "0", "pesoRsi", "0", "pesoMacd", "0")));
        assertTrue(pesos.getMessage().contains("mayor que 0"));
    }

    @Test
    void candidatosDeCadaEstrategia() {
        assertEquals(9, FabricaEstrategias.candidatos("cruce").tamanio());
        assertEquals(9, FabricaEstrategias.candidatos("rsi").tamanio());
        assertEquals(3, FabricaEstrategias.candidatos("macd").tamanio());
        assertEquals(4, FabricaEstrategias.candidatos("combinada").tamanio());
        assertThrows(IllegalArgumentException.class, () -> FabricaEstrategias.candidatos("magia"));
    }
}
