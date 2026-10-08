package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

/**
 * Combina varias estrategias por votación ponderada.
 *
 * <p>Cada estrategia vota su señal con un peso igual a peso × confianza. El
 * puntaje de cada señal es la suma de sus votos dividida entre la suma de los
 * pesos (queda entre 0 y 1). Gana la señal con mayor puntaje, y ese puntaje es la
 * confianza. Desempates, por prudencia: si empatan MANTENER y otra, gana
 * MANTENER; si empatan COMPRAR y VENDER, las estrategias se contradicen y se
 * devuelve MANTENER.
 *
 * <p>Por defecto combina {@link CruceDeMedias}, {@link EstrategiaRsi} y
 * {@link EstrategiaMacd} con peso 1 cada una.
 * Complejidad de {@link #evaluar}: la suma de las complejidades de las componentes, O(n).
 */
public class EstrategiaCombinada implements Estrategia {

    /**
     * Una estrategia con su peso en la votación.
     *
     * @param estrategia la estrategia
     * @param peso       peso (0 o más)
     */
    public record Componente(Estrategia estrategia, double peso) {

        /**
         * Valida los campos.
         *
         * @throws IllegalArgumentException si el peso es negativo o no es finito
         */
        public Componente {
            Objects.requireNonNull(estrategia, "estrategia");
            if (!(peso >= 0) || Double.isInfinite(peso)) {
                throw new IllegalArgumentException("El peso debe ser un número de 0 o más: " + peso);
            }
        }
    }

    private final Lista<Componente> componentes = new Lista<>();
    private final double sumaPesos;

    /** Cruce, RSI y MACD con sus parámetros por defecto y peso 1 cada una. */
    public EstrategiaCombinada() {
        this(1, 1, 1);
    }

    /**
     * Cruce, RSI y MACD con sus parámetros por defecto y los pesos dados.
     *
     * @param pesoCruce peso del cruce de medias
     * @param pesoRsi   peso del RSI
     * @param pesoMacd  peso del MACD
     */
    public EstrategiaCombinada(double pesoCruce, double pesoRsi, double pesoMacd) {
        this(listaDe(new Componente(new CruceDeMedias(), pesoCruce),
                new Componente(new EstrategiaRsi(), pesoRsi),
                new Componente(new EstrategiaMacd(), pesoMacd)));
    }

    /**
     * Combina las estrategias dadas.
     *
     * @param componentes estrategias con sus pesos (al menos una, con suma de pesos positiva)
     * @throws IllegalArgumentException si no hay componentes o todos los pesos son 0
     */
    public EstrategiaCombinada(Lista<Componente> componentes) {
        double suma = 0;
        for (Componente componente : componentes) {
            this.componentes.agregar(componente);
            suma += componente.peso();
        }
        if (this.componentes.estaVacia() || !(suma > 0)) {
            throw new IllegalArgumentException("La estrategia combinada necesita al menos un peso mayor que 0");
        }
        this.sumaPesos = suma;
    }

    private static Lista<Componente> listaDe(Componente... componentes) {
        Lista<Componente> lista = new Lista<>();
        for (Componente componente : componentes) {
            lista.agregar(componente);
        }
        return lista;
    }

    @Override
    public String nombre() {
        return "combinada";
    }

    @Override
    public Map<String, Object> parametros() {
        Map<String, Object> pesos = new LinkedHashMap<>();
        Map<String, Object> estrategias = new LinkedHashMap<>();
        for (Componente componente : componentes) {
            pesos.put(componente.estrategia().nombre(), componente.peso());
            estrategias.put(componente.estrategia().nombre(), componente.estrategia().parametros());
        }
        Map<String, Object> parametros = new LinkedHashMap<>();
        parametros.put("pesos", pesos);
        parametros.put("estrategias", estrategias);
        return parametros;
    }

    @Override
    public int velasMinimas() {
        int maximo = 0;
        for (Componente componente : componentes) {
            maximo = Math.max(maximo, componente.estrategia().velasMinimas());
        }
        return maximo;
    }

    /**
     * Evalúa cada componente por separado.
     *
     * @param velas velas hasta ahora
     * @return nombre de la estrategia → su decisión, en orden
     */
    public Map<String, Decision> evaluarComponentes(ListaDoble<Vela> velas) {
        Map<String, Decision> decisiones = new LinkedHashMap<>();
        for (Componente componente : componentes) {
            decisiones.put(componente.estrategia().nombre(), componente.estrategia().evaluar(velas));
        }
        return decisiones;
    }

    @Override
    public Decision evaluar(ListaDoble<Vela> velas) {
        // Basta con que una componente pueda opinar; si ninguna puede, faltan velas.
        int minimoParaOpinar = Integer.MAX_VALUE;
        for (Componente componente : componentes) {
            minimoParaOpinar = Math.min(minimoParaOpinar, componente.estrategia().velasMinimas());
        }
        if (velas == null || velas.tamanio() < minimoParaOpinar) {
            return Apoyo.faltanVelas(velas, minimoParaOpinar);
        }
        double[] puntaje = new double[Senal.values().length];
        for (Componente componente : componentes) {
            Decision decision = componente.estrategia().evaluar(velas);
            puntaje[decision.senal().ordinal()] += componente.peso() * decision.confianza();
        }
        for (int i = 0; i < puntaje.length; i++) {
            puntaje[i] /= sumaPesos;
        }
        double comprar = puntaje[Senal.COMPRAR.ordinal()];
        double vender = puntaje[Senal.VENDER.ordinal()];
        double mantener = puntaje[Senal.MANTENER.ordinal()];

        Senal ganadora = Senal.MANTENER;
        double confianza = mantener;
        String detalle;
        if (comprar > mantener && comprar > vender) {
            ganadora = Senal.COMPRAR;
            confianza = comprar;
            detalle = "gana COMPRAR";
        } else if (vender > mantener && vender > comprar) {
            ganadora = Senal.VENDER;
            confianza = vender;
            detalle = "gana VENDER";
        } else if (comprar == vender && comprar > mantener) {
            detalle = "COMPRAR y VENDER empatan, las estrategias se contradicen y se mantiene";
        } else {
            detalle = "gana MANTENER";
        }
        String motivo = String.format(Locale.ROOT,
                "Votación ponderada: COMPRAR %.2f, VENDER %.2f, MANTENER %.2f; %s.", comprar, vender, mantener, detalle);
        return Apoyo.decidir(velas, ganadora, confianza, motivo);
    }

    /** Frases de las estrategias que votaron lo mismo que la decisión final. */
    @Override
    public Lista<String> justificacion(ListaDoble<Vela> velas, Decision decision) {
        Lista<String> frases = new Lista<>();
        for (Map.Entry<String, Decision> entrada : evaluarComponentes(velas).entrySet()) {
            if (entrada.getValue().senal() == decision.senal()) {
                frases.agregar(entrada.getKey() + ": " + entrada.getValue().motivo());
            }
        }
        if (frases.estaVacia()) {
            frases.agregar(decision.motivo());
        }
        return frases;
    }

    @Override
    public Map<String, Double> indicadoresActuales(ListaDoble<Vela> velas) {
        Map<String, Double> valores = new LinkedHashMap<>();
        for (Componente componente : componentes) {
            valores.putAll(componente.estrategia().indicadoresActuales(velas));
        }
        return valores;
    }
}
