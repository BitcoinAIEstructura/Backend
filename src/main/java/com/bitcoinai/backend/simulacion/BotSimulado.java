package com.bitcoinai.backend.simulacion;

import com.bitcoinai.backend.estrategia.Decision;
import com.bitcoinai.backend.estrategia.Estrategia;
import com.bitcoinai.backend.estrategia.Senal;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.mercado.FuenteDeMercado;
import com.bitcoinai.backend.mercado.VelasCerradas;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Locale;
import java.util.Objects;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.LongSupplier;

/**
 * Bot de trading simulado. Nunca opera con dinero real.
 *
 * <p>Cada {@code segundosEntreCiclos} (con un {@link ScheduledExecutorService}) ejecuta un ciclo:
 * <ol>
 *   <li>Pide las velas más recientes (solo las cerradas) y el precio actual.</li>
 *   <li>Consulta la estrategia (por defecto la combinada) y registra su decisión
 *       con el motivo en el historial. Si la señal cambió respecto de la anterior,
 *       la publica como evento "senal".</li>
 *   <li>Si hay posición y el precio cayó {@code stopLoss} o más desde el costo
 *       promedio, vende todo (stop-loss); si subió {@code takeProfit} o más, vende
 *       todo (take-profit). Esto tiene prioridad sobre la estrategia.</li>
 *   <li>Si no, con COMPRAR y sin posición, compra por {@code riesgo} × saldo; con
 *       VENDER y con posición, vende todo el BTC.</li>
 *   <li>Procesa las órdenes pendientes de la cola, en orden FIFO: el bot hace
 *       de motor de ejecución.</li>
 * </ol>
 * Un ciclo que falla (por ejemplo, porque Binance no responde) se registra como
 * error y el bot sigue con el próximo.
 */
public class BotSimulado {

    /** Compra mínima en USDT; con menos saldo el bot no compra. */
    public static final double COMPRA_MINIMA = 1.0;

    /** Límite de órdenes procesadas por ciclo, por si otro hilo sigue creando. */
    private static final int MAXIMO_PROCESADAS_POR_CICLO = 100;

    private final LibroDeOrdenes libro;
    private final FuenteDeMercado fuente;
    private final Estrategia estrategia;
    private final String simbolo;
    private final LongSupplier reloj;
    private final Object cerrojoCiclo = new Object();

    private ScheduledExecutorService planificador; // protegido por "this"
    private volatile boolean activo;
    private volatile ConfiguracionBot configuracion = ConfiguracionBot.porDefecto();
    private final AtomicLong ciclos = new AtomicLong();
    private volatile Long ultimoCiclo;
    private volatile Decision ultimaDecision;
    private volatile String ultimoError;
    private volatile PublicadorEventos publicador = PublicadorEventos.NINGUNO;
    private volatile Senal ultimaSenalPublicada;

    /**
     * Crea el bot con el reloj del sistema.
     *
     * @param libro      libro de órdenes compartido con la API
     * @param fuente     velas y precio
     * @param estrategia estrategia a consultar (normalmente la combinada)
     * @param simbolo    par, por ejemplo "BTCUSDT"
     */
    public BotSimulado(LibroDeOrdenes libro, FuenteDeMercado fuente, Estrategia estrategia, String simbolo) {
        this(libro, fuente, estrategia, simbolo, System::currentTimeMillis);
    }

    /**
     * Crea el bot.
     *
     * @param libro      libro de órdenes compartido con la API
     * @param fuente     velas y precio
     * @param estrategia estrategia a consultar
     * @param simbolo    par
     * @param reloj      momento actual en ms (en pruebas, uno controlable)
     */
    public BotSimulado(LibroDeOrdenes libro, FuenteDeMercado fuente, Estrategia estrategia, String simbolo,
                       LongSupplier reloj) {
        this.libro = Objects.requireNonNull(libro, "libro");
        this.fuente = Objects.requireNonNull(fuente, "fuente");
        this.estrategia = Objects.requireNonNull(estrategia, "estrategia");
        this.simbolo = Objects.requireNonNull(simbolo, "simbolo");
        this.reloj = Objects.requireNonNull(reloj, "reloj");
    }

    /**
     * Indica a quién avisar cuando cambia la decisión de la estrategia (evento "senal").
     *
     * @param nuevoPublicador destino de los eventos
     */
    public void usarPublicador(PublicadorEventos nuevoPublicador) {
        this.publicador = Objects.requireNonNull(nuevoPublicador, "publicador");
    }

    /**
     * Pone en marcha el bot; el primer ciclo empieza enseguida.
     *
     * @param nuevaConfiguracion configuración a usar
     * @return el estado
     * @throws IllegalStateException si ya estaba en marcha
     */
    public synchronized EstadoBot iniciar(ConfiguracionBot nuevaConfiguracion) {
        Objects.requireNonNull(nuevaConfiguracion, "configuracion");
        if (activo) {
            throw new IllegalStateException("El bot ya está en marcha; deténlo antes de iniciarlo de nuevo");
        }
        configuracion = nuevaConfiguracion;
        ultimaSenalPublicada = null; // la primera decisión tras iniciar siempre se publica
        planificador = Executors.newSingleThreadScheduledExecutor(tarea -> {
            Thread hilo = new Thread(tarea, "bot-simulado");
            hilo.setDaemon(true);
            return hilo;
        });
        // Con "fixed delay" un ciclo nunca se superpone con el siguiente.
        planificador.scheduleWithFixedDelay(this::ejecutarCiclo, 0, nuevaConfiguracion.segundosEntreCiclos(), TimeUnit.SECONDS);
        activo = true;
        libro.registrarEvento(TipoEvento.BOT_INICIADO, null, String.format(Locale.ROOT,
                "Bot iniciado: estrategia %s, cada %d s, velas de %s, riesgo %.0f %%, stop-loss %.1f %%, take-profit %.1f %%.",
                estrategia.nombre(), nuevaConfiguracion.segundosEntreCiclos(), nuevaConfiguracion.intervalo(),
                nuevaConfiguracion.riesgo() * 100, nuevaConfiguracion.stopLoss() * 100,
                nuevaConfiguracion.takeProfit() * 100));
        return estado();
    }

    /**
     * Detiene el bot (deja terminar el ciclo en curso). Si ya estaba detenido no hace nada.
     *
     * @return el estado
     */
    public synchronized EstadoBot detener() {
        if (activo) {
            planificador.shutdown();
            planificador = null;
            activo = false;
            libro.registrarEvento(TipoEvento.BOT_DETENIDO, null, "Bot detenido.");
        }
        return estado();
    }

    /**
     * Devuelve el estado actual.
     *
     * @return el estado
     */
    public EstadoBot estado() {
        return new EstadoBot(activo, estrategia.nombre(), configuracion, ciclos.get(),
                ultimoCiclo, ultimaDecision, ultimoError);
    }

    /**
     * Ejecuta un ciclo completo ahora mismo (lo llama el planificador; también
     * sirve en pruebas). Nunca lanza excepciones: los errores quedan en el estado
     * y en el historial.
     */
    public void ejecutarCiclo() {
        synchronized (cerrojoCiclo) {
            ConfiguracionBot config = configuracion;
            try {
                ListaDoble<Vela> velas = VelasCerradas.filtrar(fuente.obtenerVelas(simbolo,
                        Intervalo.desdeCodigo(config.intervalo()), config.cantidadVelas()), reloj.getAsLong());
                double precio = fuente.obtenerPrecioActual(simbolo);
                EstadoCartera cartera = libro.estadoCartera(precio);
                Decision decision = estrategia.evaluar(velas);
                ultimaDecision = decision;
                libro.registrarEvento(TipoEvento.DECISION_BOT, null, String.format(Locale.ROOT,
                        "El bot decidió %s (confianza %.2f): %s", decision.senal(), decision.confianza(), decision.motivo()));
                if (decision.senal() != ultimaSenalPublicada) {
                    publicador.publicar("senal", decision);
                    ultimaSenalPublicada = decision.senal();
                }

                boolean hayPosicion = cartera.btc() > 0;
                if (!(hayPosicion && revisarSalidaDeRiesgo(cartera, precio, config))) {
                    actuarSegunDecision(decision, cartera, hayPosicion, config);
                }
                procesarPendientes();
                ultimoError = null;
            } catch (RuntimeException e) {
                ultimoError = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                libro.registrarEvento(TipoEvento.ERROR_BOT, null, "El ciclo del bot falló: " + ultimoError);
            } finally {
                ciclos.incrementAndGet();
                ultimoCiclo = reloj.getAsLong();
            }
        }
    }

    /** Stop-loss y take-profit. Devuelve true si creó una orden de venta. */
    private boolean revisarSalidaDeRiesgo(EstadoCartera cartera, double precio, ConfiguracionBot config) {
        double costo = cartera.costoPromedio();
        if (costo <= 0) {
            return false;
        }
        double variacion = precio / costo - 1;
        TipoEvento tipo = null;
        if (variacion <= -config.stopLoss()) {
            tipo = TipoEvento.STOP_LOSS;
        } else if (variacion >= config.takeProfit()) {
            tipo = TipoEvento.TAKE_PROFIT;
        }
        if (tipo == null) {
            return false;
        }
        String nombre = tipo == TipoEvento.STOP_LOSS ? "stop-loss" : "take-profit";
        String detalle = String.format(Locale.ROOT, "%s: el precio %.2f está %+.2f %% respecto del costo promedio %.2f",
                nombre, precio, variacion * 100, costo);
        Orden orden = libro.crearVentaTotal(detalle);
        libro.registrarEvento(tipo, orden.id(), "El bot vende todo por " + detalle + ".");
        return true;
    }

    private void actuarSegunDecision(Decision decision, EstadoCartera cartera, boolean hayPosicion, ConfiguracionBot config) {
        if (decision.senal() == Senal.COMPRAR && !hayPosicion) {
            double monto = cartera.saldoUsdt() * config.riesgo();
            if (monto >= COMPRA_MINIMA) {
                libro.crearCompra(monto, "señal del bot: " + decision.motivo());
            }
        } else if (decision.senal() == Senal.VENDER && hayPosicion) {
            libro.crearVentaTotal("señal del bot: " + decision.motivo());
        }
    }

    private void procesarPendientes() {
        for (int i = 0; i < MAXIMO_PROCESADAS_POR_CICLO; i++) {
            if (libro.procesarSiguiente().isEmpty()) {
                return;
            }
        }
    }
}
