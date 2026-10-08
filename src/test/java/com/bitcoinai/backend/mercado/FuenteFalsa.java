package com.bitcoinai.backend.mercado;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Fuente de mercado en memoria para pruebas: no usa internet, cuenta cuántas
 * veces la consultan y puede configurarse para fallar.
 */
public class FuenteFalsa implements FuenteDeMercado {

    private volatile ListaDoble<Vela> velas;
    private volatile double precio;
    private volatile RuntimeException error;
    private final AtomicInteger llamadasVelas = new AtomicInteger();
    private final AtomicInteger llamadasPrecio = new AtomicInteger();

    public FuenteFalsa(ListaDoble<Vela> velas, double precio) {
        this.velas = velas;
        this.precio = precio;
    }

    /** Fuente con 500 velas diarias sintéticas y precio 100. */
    public FuenteFalsa() {
        this(generarVelas(500, Intervalo.D1), 100.0);
    }

    /**
     * Genera velas válidas y consecutivas: la vela i abre en 100 + i, con máximo
     * +5, mínimo -5 y cierre +1.
     */
    public static ListaDoble<Vela> generarVelas(int cantidad, Intervalo intervalo) {
        ListaDoble<Vela> resultado = new ListaDoble<>();
        long inicio = 1_700_000_000_000L;
        for (int i = 0; i < cantidad; i++) {
            long apertura = inicio + i * intervalo.milisegundos();
            double precioApertura = 100.0 + i;
            resultado.agregarFinal(new Vela(apertura, precioApertura, precioApertura + 5,
                    precioApertura - 5, precioApertura + 1, 10.0,
                    apertura + intervalo.milisegundos() - 1));
        }
        return resultado;
    }

    /** Devuelve una copia de las últimas {@code cantidad} velas. */
    @Override
    public ListaDoble<Vela> obtenerVelas(String simbolo, Intervalo intervalo, int cantidad) {
        llamadasVelas.incrementAndGet();
        if (error != null) {
            throw error;
        }
        ListaDoble<Vela> origen = velas;
        ListaDoble<Vela> copia = new ListaDoble<>();
        int saltar = Math.max(0, origen.tamanio() - cantidad);
        int i = 0;
        for (Vela vela : origen) {
            if (i++ >= saltar) {
                copia.agregarFinal(vela);
            }
        }
        return copia;
    }

    @Override
    public double obtenerPrecioActual(String simbolo) {
        llamadasPrecio.incrementAndGet();
        if (error != null) {
            throw error;
        }
        return precio;
    }

    public void setVelas(ListaDoble<Vela> velas) {
        this.velas = velas;
    }

    public void setPrecio(double precio) {
        this.precio = precio;
    }

    /** Hace que las próximas llamadas lancen este error; null para que vuelvan a funcionar. */
    public void setError(RuntimeException error) {
        this.error = error;
    }

    public int getLlamadasVelas() {
        return llamadasVelas.get();
    }

    public int getLlamadasPrecio() {
        return llamadasPrecio.get();
    }
}
