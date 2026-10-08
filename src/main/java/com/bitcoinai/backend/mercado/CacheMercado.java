package com.bitcoinai.backend.mercado;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.time.Duration;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongSupplier;
import java.util.function.Supplier;

/**
 * Envuelve cualquier {@link FuenteDeMercado} y guarda sus respuestas en memoria
 * durante un tiempo (TTL) para no repetir peticiones iguales.
 *
 * <p>Cada combinación de símbolo, intervalo y cantidad se guarda por separado,
 * igual que el precio de cada símbolo. Los errores no se guardan. Es segura para
 * usarse desde varios hilos; si dos hilos piden lo mismo a la vez puede que ambos
 * consulten la fuente, lo cual es aceptable.
 */
public class CacheMercado implements FuenteDeMercado {

    private final FuenteDeMercado fuente;
    private final long ttlMilis;
    private final LongSupplier relojMilis;
    private final Map<String, Entrada> entradas = new ConcurrentHashMap<>();

    private record Entrada(Object valor, long expiraEn) {
    }

    /**
     * Crea la caché.
     *
     * @param fuente fuente real a la que se consulta cuando no hay dato vigente
     * @param ttl    cuánto tiempo es válido un dato guardado (0 desactiva la caché)
     */
    public CacheMercado(FuenteDeMercado fuente, Duration ttl) {
        this(fuente, ttl, () -> System.nanoTime() / 1_000_000L);
    }

    /** Igual que el constructor público, con un reloj controlable para las pruebas. */
    CacheMercado(FuenteDeMercado fuente, Duration ttl, LongSupplier relojMilis) {
        this.fuente = Objects.requireNonNull(fuente, "fuente");
        Objects.requireNonNull(ttl, "ttl");
        if (ttl.isNegative()) {
            throw new IllegalArgumentException("El TTL no puede ser negativo");
        }
        this.ttlMilis = ttl.toMillis();
        this.relojMilis = Objects.requireNonNull(relojMilis, "relojMilis");
    }

    /**
     * {@inheritDoc}
     *
     * <p>Devuelve una copia de la lista guardada, para que quien la reciba pueda
     * modificarla sin dañar la caché. Complejidad: O(1) para consultar la caché
     * más O(n) para copiar las n velas.
     */
    @Override
    public ListaDoble<Vela> obtenerVelas(String simbolo, Intervalo intervalo, int cantidad) {
        String clave = "velas|" + simbolo + "|" + intervalo + "|" + cantidad;
        @SuppressWarnings("unchecked")
        ListaDoble<Vela> velas = (ListaDoble<Vela>) obtener(clave,
                () -> fuente.obtenerVelas(simbolo, intervalo, cantidad));
        return copiar(velas);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Complejidad: O(1) si el precio está en caché.
     */
    @Override
    public double obtenerPrecioActual(String simbolo) {
        return (Double) obtener("precio|" + simbolo, () -> fuente.obtenerPrecioActual(simbolo));
    }

    private Object obtener(String clave, Supplier<Object> cargar) {
        long ahora = relojMilis.getAsLong();
        Entrada entrada = entradas.get(clave);
        if (entrada != null && ahora < entrada.expiraEn()) {
            return entrada.valor();
        }
        Object valor = cargar.get();
        entradas.put(clave, new Entrada(valor, ahora + ttlMilis));
        return valor;
    }

    private static ListaDoble<Vela> copiar(ListaDoble<Vela> original) {
        ListaDoble<Vela> copia = new ListaDoble<>();
        for (Vela vela : original) {
            copia.agregarFinal(vela);
        }
        return copia;
    }
}
