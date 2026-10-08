package com.bitcoinai.backend.indicadores;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Operaciones comunes sobre series de puntos que usan varios indicadores.
 */
public final class Series {

    private Series() {
    }

    /**
     * Convierte las velas en la serie de sus precios de cierre.
     * Complejidad: O(n), un recorrido hacia adelante.
     *
     * @param velas velas de la más antigua a la más reciente (null se trata como vacía)
     * @return un punto (tiempoApertura, cierre) por vela
     */
    public static ListaDoble<PuntoIndicador> cierres(ListaDoble<Vela> velas) {
        ListaDoble<PuntoIndicador> serie = new ListaDoble<>();
        if (velas != null) {
            for (Vela vela : velas) {
                serie.agregarFinal(new PuntoIndicador(vela.tiempoApertura(), vela.cierre()));
            }
        }
        return serie;
    }

    /**
     * Devuelve los {@code n} elementos más recientes (los del final), en orden cronológico.
     *
     * <p><b>Por qué se recorre hacia atrás:</b> lo que interesa son los valores más
     * recientes, que están en la cola de la lista. Empezando por la cola con el
     * iterador hacia atrás (enlaces "anterior") se visitan solo esos {@code n}
     * elementos y se paran ahí; recorriendo hacia adelante habría que pasar
     * primero por todos los antiguos. Cada uno se agrega al inicio del resultado
     * para que quede en orden cronológico.
     * Complejidad: O(min(n, tamaño)).
     *
     * @param lista lista de la más antigua a la más reciente
     * @param n     cuántos elementos tomar (0 o más)
     * @param <T>   tipo de los elementos
     * @return una lista nueva con los últimos n (o todos, si hay menos)
     * @throws IllegalArgumentException si n es negativo
     */
    public static <T> ListaDoble<T> ultimos(ListaDoble<T> lista, int n) {
        if (n < 0) {
            throw new IllegalArgumentException("n no puede ser negativo: " + n);
        }
        ListaDoble<T> resultado = new ListaDoble<>();
        Iterator<T> haciaAtras = lista.iteradorAtras();
        while (resultado.tamanio() < n && haciaAtras.hasNext()) {
            resultado.agregarInicio(haciaAtras.next());
        }
        return resultado;
    }

    /**
     * Media móvil exponencial de una serie de puntos.
     *
     * <p>Fórmula: α = 2 / (periodo + 1); EMA₀ = media simple de los primeros
     * {@code periodo} valores; EMAₜ = α·xₜ + (1 − α)·EMAₜ₋₁. El primer punto sale
     * en la posición {@code periodo − 1}. Con periodo 1, α = 1 y la EMA es igual a la serie.
     * Complejidad: O(n), un recorrido hacia adelante.
     *
     * @param serie   puntos en orden cronológico
     * @param periodo periodo (1 o más)
     * @return la EMA, con {@code max(0, n − periodo + 1)} puntos
     * @throws IllegalArgumentException si el periodo es menor que 1
     */
    public static ListaDoble<PuntoIndicador> ema(ListaDoble<PuntoIndicador> serie, int periodo) {
        if (periodo < 1) {
            throw new IllegalArgumentException("El periodo debe ser al menos 1: " + periodo);
        }
        double alfa = 2.0 / (periodo + 1);
        ListaDoble<PuntoIndicador> resultado = new ListaDoble<>();
        int vistos = 0;
        double suma = 0;
        double ema = 0;
        for (PuntoIndicador punto : serie) {
            if (vistos < periodo) {
                suma += punto.valor();
                vistos++;
                if (vistos == periodo) {
                    ema = suma / periodo;
                    resultado.agregarFinal(new PuntoIndicador(punto.tiempo(), ema));
                }
            } else {
                ema = alfa * punto.valor() + (1 - alfa) * ema;
                resultado.agregarFinal(new PuntoIndicador(punto.tiempo(), ema));
            }
        }
        return resultado;
    }

    /**
     * Resta dos series alineadas por posición (a − b). Ambas deben tener el mismo
     * tamaño; el tiempo de cada punto se toma de {@code b}.
     * Complejidad: O(n), recorre las dos a la vez hacia adelante.
     */
    static ListaDoble<PuntoIndicador> restar(ListaDoble<PuntoIndicador> a, ListaDoble<PuntoIndicador> b) {
        ListaDoble<PuntoIndicador> resultado = new ListaDoble<>();
        Iterator<PuntoIndicador> itA = a.iteradorAdelante();
        Iterator<PuntoIndicador> itB = b.iteradorAdelante();
        while (itA.hasNext() && itB.hasNext()) {
            PuntoIndicador pa = itA.next();
            PuntoIndicador pb = itB.next();
            resultado.agregarFinal(new PuntoIndicador(pb.tiempo(), pa.valor() - pb.valor()));
        }
        return resultado;
    }

    /** Parámetros con un solo "periodo", para los indicadores que solo usan ese. */
    static Map<String, Object> soloPeriodo(int periodo) {
        Map<String, Object> parametros = new LinkedHashMap<>();
        parametros.put("periodo", periodo);
        return parametros;
    }
}
