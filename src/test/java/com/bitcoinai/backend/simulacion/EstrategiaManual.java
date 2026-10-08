package com.bitcoinai.backend.simulacion;

import com.bitcoinai.backend.estrategia.Decision;
import com.bitcoinai.backend.estrategia.Estrategia;
import com.bitcoinai.backend.estrategia.Senal;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;

/** Estrategia falsa para pruebas: devuelve la señal que se le indique. */
class EstrategiaManual implements Estrategia {

    private volatile Senal senal = Senal.MANTENER;
    volatile int evaluaciones;

    void decir(Senal nueva) {
        senal = nueva;
    }

    @Override
    public String nombre() {
        return "manual";
    }

    @Override
    public Map<String, Object> parametros() {
        return new LinkedHashMap<>();
    }

    @Override
    public int velasMinimas() {
        return 1;
    }

    @Override
    public Decision evaluar(ListaDoble<Vela> velas) {
        evaluaciones++;
        long tiempo = velas.estaVacia() ? 0 : velas.ultimo().tiempoApertura();
        double precio = velas.estaVacia() ? 0 : velas.ultimo().cierre();
        return new Decision(tiempo, senal, precio, senal == Senal.MANTENER ? 0.25 : 0.9,
                "la prueba pidió " + senal);
    }

    @Override
    public Map<String, Double> indicadoresActuales(ListaDoble<Vela> velas) {
        return new LinkedHashMap<>();
    }
}
