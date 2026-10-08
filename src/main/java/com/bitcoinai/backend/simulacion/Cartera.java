package com.bitcoinai.backend.simulacion;

import java.util.Locale;

/**
 * Cartera simulada: saldo en USDT, BTC y costo de la posición.
 *
 * <p>Contabilidad:
 * <ul>
 *   <li><b>Compra</b> de M USDT al precio P con comisión c: se pagan M USDT, la
 *       comisión es M·c y se reciben (M − M·c) / P BTC. El costo de la posición
 *       aumenta en M (la comisión forma parte del costo).</li>
 *   <li><b>Venta</b> de B BTC al precio P: se obtienen B·P USDT brutos, se paga
 *       B·P·c de comisión y se recibe el resto. El costo de la posición baja en
 *       proporción a lo vendido, así que el costo promedio no cambia. La ganancia
 *       realizada es lo recibido menos el costo de lo vendido.</li>
 * </ul>
 * No es segura para varios hilos: la protege el {@link LibroDeOrdenes}.
 * Todas las operaciones son O(1).
 */
public class Cartera {

    /** Saldo inicial por defecto, en USDT. */
    public static final double SALDO_INICIAL_POR_DEFECTO = 10_000;

    /** Diferencias menores que esto se consideran redondeo. */
    private static final double TOLERANCIA = 1e-9;

    /**
     * Resultado de ejecutar una operación.
     *
     * @param montoUsdt   USDT pagados (compra) o brutos obtenidos (venta)
     * @param cantidadBtc BTC recibidos o entregados
     * @param comision    comisión cobrada en USDT
     */
    public record Ejecucion(double montoUsdt, double cantidadBtc, double comision) {
    }

    private final double saldoInicial;
    private double saldoUsdt;
    private double btc;
    private double costoPosicion;
    private double gananciaRealizada;
    private double comisionesPagadas;

    /** Cartera con {@value #SALDO_INICIAL_POR_DEFECTO} USDT. */
    public Cartera() {
        this(SALDO_INICIAL_POR_DEFECTO);
    }

    /**
     * Crea la cartera.
     *
     * @param saldoInicial USDT iniciales (mayor que 0)
     * @throws IllegalArgumentException si el saldo no es positivo
     */
    public Cartera(double saldoInicial) {
        if (!(saldoInicial > 0) || Double.isInfinite(saldoInicial)) {
            throw new IllegalArgumentException("El saldo inicial debe ser positivo: " + saldoInicial);
        }
        this.saldoInicial = saldoInicial;
        this.saldoUsdt = saldoInicial;
    }

    /**
     * Reconstruye una cartera guardada.
     *
     * @param datos datos guardados
     */
    public Cartera(DatosCartera datos) {
        this(datos.saldoInicial());
        this.saldoUsdt = datos.saldoUsdt();
        this.btc = datos.btc();
        this.costoPosicion = datos.btc() > 0 ? datos.costoPosicion() : 0;
        this.gananciaRealizada = datos.gananciaRealizada();
        this.comisionesPagadas = datos.comisionesPagadas();
    }

    /**
     * Devuelve los datos necesarios para reconstruirla.
     * Complejidad: O(1).
     *
     * @return los datos
     */
    public DatosCartera datos() {
        return new DatosCartera(saldoInicial, saldoUsdt, btc, costoPosicion, gananciaRealizada, comisionesPagadas);
    }

    /**
     * Compra BTC por un monto en USDT.
     *
     * @param montoUsdt USDT a gastar, comisión incluida
     * @param precio    precio de 1 BTC
     * @param comision  comisión (0,001 = 0,1 %)
     * @return lo ejecutado
     * @throws OperacionRechazadaException si no alcanza el saldo
     */
    public Ejecucion comprar(double montoUsdt, double precio, double comision) {
        if (montoUsdt > saldoUsdt + TOLERANCIA) {
            throw new OperacionRechazadaException(String.format(Locale.ROOT,
                    "Saldo insuficiente: la compra necesita %.2f USDT y hay %.2f", montoUsdt, saldoUsdt));
        }
        double costoComision = montoUsdt * comision;
        double comprado = (montoUsdt - costoComision) / precio;
        saldoUsdt = Math.max(0, saldoUsdt - montoUsdt);
        btc += comprado;
        costoPosicion += montoUsdt;
        comisionesPagadas += costoComision;
        return new Ejecucion(montoUsdt, comprado, costoComision);
    }

    /**
     * Vende BTC por un monto en USDT (brutos, antes de comisión).
     *
     * @param montoUsdt valor en USDT del BTC a vender
     * @param precio    precio de 1 BTC
     * @param comision  comisión (0,001 = 0,1 %)
     * @return lo ejecutado
     * @throws OperacionRechazadaException si no hay BTC suficiente
     */
    public Ejecucion vender(double montoUsdt, double precio, double comision) {
        double cantidad = montoUsdt / precio;
        if (cantidad > btc + TOLERANCIA) {
            throw new OperacionRechazadaException(String.format(Locale.ROOT,
                    "BTC insuficiente: la venta necesita %.8f BTC y hay %.8f", cantidad, btc));
        }
        return venderCantidad(Math.min(cantidad, btc), precio, comision);
    }

    /**
     * Vende todo el BTC.
     *
     * @param precio   precio de 1 BTC
     * @param comision comisión (0,001 = 0,1 %)
     * @return lo ejecutado
     * @throws OperacionRechazadaException si no hay BTC
     */
    public Ejecucion venderTodo(double precio, double comision) {
        if (btc <= 0) {
            throw new OperacionRechazadaException("No hay BTC para vender");
        }
        return venderCantidad(btc, precio, comision);
    }

    private Ejecucion venderCantidad(double cantidad, double precio, double comision) {
        double bruto = cantidad * precio;
        double costoComision = bruto * comision;
        double costoVendido = costoPosicion * (cantidad / btc);
        saldoUsdt += bruto - costoComision;
        gananciaRealizada += bruto - costoComision - costoVendido;
        comisionesPagadas += costoComision;
        btc -= cantidad;
        costoPosicion -= costoVendido;
        if (btc < TOLERANCIA * 1e-3) { // restos de redondeo
            btc = 0;
            costoPosicion = 0;
        }
        return new Ejecucion(bruto, cantidad, costoComision);
    }

    /**
     * Devuelve el USDT disponible.
     *
     * @return el saldo en USDT
     */
    public double getSaldoUsdt() {
        return saldoUsdt;
    }

    /**
     * Devuelve el BTC en cartera.
     *
     * @return la cantidad de BTC
     */
    public double getBtc() {
        return btc;
    }

    /**
     * Devuelve el costo promedio por BTC de la posición actual, con comisiones.
     *
     * @return el costo promedio, o 0 si no hay BTC
     */
    public double costoPromedio() {
        return btc > 0 ? costoPosicion / btc : 0;
    }

    /**
     * Devuelve el valor total al precio dado.
     *
     * @param precio precio de 1 BTC
     * @return saldo en USDT + valor del BTC
     */
    public double valorTotal(double precio) {
        return saldoUsdt + btc * precio;
    }

    /**
     * Devuelve la ganancia o pérdida total desde el inicio, al precio dado.
     *
     * @param precio precio de 1 BTC
     * @return valor total − saldo inicial (negativo si hay pérdida)
     */
    public double gananciaTotal(double precio) {
        return valorTotal(precio) - saldoInicial;
    }

    /**
     * Devuelve la ganancia o pérdida de la posición abierta, al precio dado.
     *
     * @param precio precio de 1 BTC
     * @return valor del BTC − lo que costó
     */
    public double gananciaNoRealizada(double precio) {
        return btc * precio - costoPosicion;
    }

    /**
     * Devuelve una foto completa de la cartera valorada al precio dado.
     *
     * @param precio precio de 1 BTC
     * @return el estado
     */
    public EstadoCartera estado(double precio) {
        double gananciaTotal = gananciaTotal(precio);
        return new EstadoCartera(precio, saldoUsdt, btc, costoPromedio(), btc * precio, valorTotal(precio),
                gananciaNoRealizada(precio), gananciaRealizada, gananciaTotal, gananciaTotal / saldoInicial,
                comisionesPagadas, saldoInicial);
    }
}
