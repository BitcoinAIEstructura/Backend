package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Estrategia falsa para pruebas: da la señal que se le indique en cada índice de
 * vela (o una señal fija en todas), y registra lo que vio en cada llamada para
 * comprobar que nunca recibe velas del futuro.
 */
class EstrategiaGuion implements Estrategia {

    private final String nombre;
    private final Map<Integer, Senal> guion = new HashMap<>();
    private final Senal porDefecto;
    private final double confianza;

    /** Cantidad de velas recibida en cada llamada. */
    final Lista<Integer> tamaniosVistos = new Lista<>();
    /** Tiempo de la última vela recibida en cada llamada. */
    final Lista<Long> tiemposVistos = new Lista<>();

    EstrategiaGuion(String nombre, Senal porDefecto, double confianza) {
        this.nombre = nombre;
        this.porDefecto = porDefecto;
        this.confianza = confianza;
    }

    /** Señal fija con la confianza dada (MANTENER siempre usa la confianza neutra). */
    static EstrategiaGuion fija(String nombre, Senal senal, double confianza) {
        return new EstrategiaGuion(nombre, senal, confianza);
    }

    /** MANTENER salvo en los índices indicados. */
    static EstrategiaGuion conGuion() {
        return new EstrategiaGuion("guion", Senal.MANTENER, 1.0);
    }

    EstrategiaGuion en(int indice, Senal senal) {
        guion.put(indice, senal);
        return this;
    }

    @Override
    public String nombre() {
        return nombre;
    }

    @Override
    public Map<String, Object> parametros() {
        Map<String, Object> parametros = new LinkedHashMap<>();
        parametros.put("nombre", nombre);
        return parametros;
    }

    @Override
    public int velasMinimas() {
        return 1;
    }

    @Override
    public Decision evaluar(ListaDoble<Vela> velas) {
        tamaniosVistos.agregar(velas.tamanio());
        tiemposVistos.agregar(velas.ultimo().tiempoApertura());
        Senal senal = guion.getOrDefault(velas.tamanio() - 1, porDefecto);
        double c = senal == Senal.MANTENER ? Apoyo.CONFIANZA_NEUTRA : confianza;
        return new Decision(velas.ultimo().tiempoApertura(), senal, velas.ultimo().cierre(), c,
                nombre + " dice " + senal + " en la vela " + (velas.tamanio() - 1) + ".");
    }

    @Override
    public Map<String, Double> indicadoresActuales(ListaDoble<Vela> velas) {
        Map<String, Double> valores = new LinkedHashMap<>();
        valores.put(nombre, 1.0);
        return valores;
    }
}
