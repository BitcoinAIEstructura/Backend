package com.bitcoinai.backend.estrategia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.estructuras.Pila;
import com.bitcoinai.backend.indicadores.MaximaCaida;
import com.bitcoinai.backend.indicadores.PuntoIndicador;
import com.bitcoinai.backend.modelo.Vela;
import java.util.Objects;

/**
 * Simula una estrategia sobre velas históricas, solo con posiciones largas.
 *
 * <p>Reglas:
 * <ul>
 *   <li><b>Sin mirar el futuro:</b> se recorre la ListaDoble de la vela más antigua
 *       a la más reciente; en cada una la estrategia recibe una lista que contiene
 *       solo las velas hasta esa (se le van agregando al final, una por vuelta).</li>
 *   <li><b>Ejecución honesta:</b> la estrategia decide con el cierre de la vela t,
 *       y la orden se ejecuta en la apertura de la vela t + 1, porque al cierre de
 *       t todavía no se podía operar a ese precio. Una señal en la última vela no
 *       llega a ejecutarse.</li>
 *   <li>COMPRAR sin posición compra con todo el efectivo; VENDER con posición vende
 *       todo. Las demás señales se ignoran.</li>
 *   <li>Cada compra y cada venta paga la comisión sobre el monto operado.</li>
 *   <li>Si al final queda una posición abierta, se cierra al último cierre.</li>
 * </ul>
 * Cada decisión se apila en una {@link Pila} (la más reciente arriba) y cada
 * operación cerrada se agrega a una {@link Lista}.
 *
 * <p>Complejidad: O(n · E), donde E es el costo de evaluar la estrategia (O(n)
 * para las de este paquete), es decir O(n²) en total.
 */
public class Backtester {

    /** Cuántas decisiones de comprar o vender se devuelven en el resultado. */
    public static final int DECISIONES_RECIENTES = 20;

    private final double capitalInicial;
    private final double comision;

    /** Backtester con 1000 USDT y comisión de 0,1 %. */
    public Backtester() {
        this(1000, 0.001);
    }

    /**
     * Crea el backtester.
     *
     * @param capitalInicial USDT al empezar (mayor que 0)
     * @param comision       comisión por operación, entre 0 y menos de 1 (0,001 = 0,1 %)
     * @throws IllegalArgumentException si algún valor está fuera de rango
     */
    public Backtester(double capitalInicial, double comision) {
        if (!(capitalInicial > 0) || Double.isInfinite(capitalInicial)) {
            throw new IllegalArgumentException("El capital inicial debe ser positivo: " + capitalInicial);
        }
        if (!(comision >= 0 && comision < 1)) {
            throw new IllegalArgumentException("La comisión debe estar entre 0 y 1: " + comision);
        }
        this.capitalInicial = capitalInicial;
        this.comision = comision;
    }

    /**
     * Ejecuta el backtest sobre todas las velas.
     *
     * @param estrategia estrategia a probar
     * @param velas      velas de la más antigua a la más reciente
     * @return el resultado con sus métricas
     */
    public ResultadoBacktest ejecutar(Estrategia estrategia, ListaDoble<Vela> velas) {
        return ejecutar(estrategia, velas, 0);
    }

    /**
     * Ejecuta el backtest operando solo desde la vela {@code inicioOperaciones}.
     * Las velas anteriores se entregan a la estrategia como historial (para
     * calentar sus indicadores), pero en ellas no se decide ni se opera.
     *
     * @param estrategia        estrategia a probar
     * @param velas             velas de la más antigua a la más reciente
     * @param inicioOperaciones índice de la primera vela en que se opera (0 = todas)
     * @return el resultado, con métricas solo del periodo operado
     * @throws IllegalArgumentException si el índice está fuera de rango
     */
    public ResultadoBacktest ejecutar(Estrategia estrategia, ListaDoble<Vela> velas, int inicioOperaciones) {
        Objects.requireNonNull(estrategia, "estrategia");
        Objects.requireNonNull(velas, "velas");
        if (inicioOperaciones < 0 || inicioOperaciones > velas.tamanio()) {
            throw new IllegalArgumentException("inicioOperaciones fuera de rango: " + inicioOperaciones);
        }

        ListaDoble<Vela> hastaAhora = new ListaDoble<>();
        Pila<Decision> decisiones = new Pila<>();
        ListaDoble<PuntoIndicador> curva = new ListaDoble<>();
        Cuenta cuenta = new Cuenta();
        Decision pendiente = null;
        Vela primera = null;
        Vela ultima = null;
        int indice = 0;

        for (Vela vela : velas) {
            hastaAhora.agregarFinal(vela);
            if (indice++ < inicioOperaciones) {
                continue; // solo historial
            }
            if (primera == null) {
                primera = vela;
            }
            ultima = vela;

            // 1) La orden decidida en la vela anterior se ejecuta en la apertura de esta.
            if (pendiente != null) {
                if (pendiente.senal() == Senal.COMPRAR && !cuenta.enPosicion) {
                    cuenta.comprar(vela.tiempoApertura(), vela.apertura());
                } else if (pendiente.senal() == Senal.VENDER && cuenta.enPosicion) {
                    cuenta.vender(vela.tiempoApertura(), vela.apertura(), pendiente.motivo());
                }
                pendiente = null;
            }

            // 2) La estrategia decide viendo solo las velas hasta esta.
            Decision decision = estrategia.evaluar(hastaAhora);
            decisiones.apilar(decision);
            if (decision.senal() != Senal.MANTENER) {
                pendiente = decision;
            }
            curva.agregarFinal(new PuntoIndicador(vela.tiempoApertura(), cuenta.valor(vela.cierre())));
        }

        if (cuenta.enPosicion) {
            cuenta.vender(ultima.tiempoApertura(), ultima.cierre(), "Cierre forzado al final del periodo.");
        }
        return armarResultado(estrategia, cuenta, decisiones, curva, primera, ultima);
    }

    private ResultadoBacktest armarResultado(Estrategia estrategia, Cuenta cuenta, Pila<Decision> decisiones,
                                             ListaDoble<PuntoIndicador> curva, Vela primera, Vela ultima) {
        int ganadoras = 0;
        double sumaGanancias = 0;
        double sumaPerdidas = 0;
        for (OperacionCerrada operacion : cuenta.operaciones) {
            if (operacion.ganancia() > 0) {
                ganadoras++;
                sumaGanancias += operacion.ganancia();
            } else {
                sumaPerdidas -= operacion.ganancia();
            }
        }
        int numeroOperaciones = cuenta.operaciones.tamanio();
        double tasaGanadoras = numeroOperaciones == 0 ? 0 : (double) ganadoras / numeroOperaciones;
        Double factorBeneficio = sumaPerdidas == 0 ? null : sumaGanancias / sumaPerdidas;

        double comprarYMantener = 0;
        if (primera != null) {
            comprarYMantener = (1 - comision) * (1 - comision) * ultima.cierre() / primera.apertura() - 1;
        }

        // La pila deja la decisión más reciente arriba: al desapilar salen de la
        // más nueva a la más vieja, que es justo el orden que interesa mostrar.
        int numeroDecisiones = decisiones.tamanio();
        Lista<Decision> recientes = new Lista<>();
        while (!decisiones.estaVacia() && recientes.tamanio() < DECISIONES_RECIENTES) {
            Decision decision = decisiones.desapilar();
            if (decision.senal() != Senal.MANTENER) {
                recientes.agregar(decision);
            }
        }

        return new ResultadoBacktest(
                estrategia.nombre(),
                estrategia.parametros(),
                capitalInicial,
                comision,
                cuenta.efectivo,
                cuenta.efectivo / capitalInicial - 1,
                comprarYMantener,
                numeroOperaciones,
                tasaGanadoras,
                MaximaCaida.dePuntos(curva).caidaMaxima(),
                factorBeneficio,
                cuenta.comisiones,
                curva.tamanio(),
                numeroDecisiones,
                primera == null ? 0 : primera.tiempoApertura(),
                ultima == null ? 0 : ultima.tiempoCierre(),
                cuenta.operaciones,
                recientes,
                curva);
    }

    /** Estado de la cuenta simulada: efectivo, BTC y la operación abierta. */
    private final class Cuenta {
        double efectivo = capitalInicial;
        double btc;
        boolean enPosicion;
        double comisiones;
        double capitalAlEntrar;
        double comisionEntrada;
        double precioEntrada;
        long tiempoEntrada;
        final Lista<OperacionCerrada> operaciones = new Lista<>();

        double valor(double precio) {
            return efectivo + btc * precio;
        }

        void comprar(long tiempo, double precio) {
            capitalAlEntrar = efectivo;
            comisionEntrada = efectivo * comision;
            btc = (efectivo - comisionEntrada) / precio;
            efectivo = 0;
            comisiones += comisionEntrada;
            precioEntrada = precio;
            tiempoEntrada = tiempo;
            enPosicion = true;
        }

        void vender(long tiempo, double precio, String motivo) {
            double bruto = btc * precio;
            double comisionSalida = bruto * comision;
            efectivo = bruto - comisionSalida;
            comisiones += comisionSalida;
            double ganancia = efectivo - capitalAlEntrar;
            operaciones.agregar(new OperacionCerrada(tiempoEntrada, precioEntrada, tiempo, precio, btc,
                    comisionEntrada + comisionSalida, ganancia, ganancia / capitalAlEntrar, motivo));
            btc = 0;
            enPosicion = false;
        }
    }
}
