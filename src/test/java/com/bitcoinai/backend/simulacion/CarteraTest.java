package com.bitcoinai.backend.simulacion;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class CarteraTest {

    private static final double C = 0.001;

    @Test
    void empiezaConDiezMilUsdtYSinBtc() {
        Cartera cartera = new Cartera();
        assertEquals(10_000, cartera.getSaldoUsdt());
        assertEquals(0, cartera.getBtc());
        assertEquals(0, cartera.costoPromedio());
        assertEquals(10_000, cartera.valorTotal(85_000));
        assertEquals(0, cartera.gananciaTotal(85_000));
    }

    @Test
    void compraDescuentaElSaldoYCobraComision() {
        Cartera cartera = new Cartera();
        Cartera.Ejecucion e = cartera.comprar(500, 100, C);
        assertEquals(500, e.montoUsdt());
        assertEquals(0.5, e.comision(), 1e-12);
        assertEquals(499.5 / 100, e.cantidadBtc(), 1e-12);
        assertEquals(9_500, cartera.getSaldoUsdt(), 1e-9);
        assertEquals(4.995, cartera.getBtc(), 1e-12);
        assertEquals(500 / 4.995, cartera.costoPromedio(), 1e-9); // la comisión forma parte del costo
    }

    @Test
    void ventaDeTodoRealizaLaGanancia() {
        Cartera cartera = new Cartera();
        cartera.comprar(500, 100, C);
        Cartera.Ejecucion e = cartera.venderTodo(110, C);
        double bruto = 4.995 * 110;
        assertEquals(bruto, e.montoUsdt(), 1e-9);
        assertEquals(bruto * C, e.comision(), 1e-12);
        assertEquals(0, cartera.getBtc());
        assertEquals(0, cartera.costoPromedio());
        assertEquals(9_500 + bruto * (1 - C), cartera.getSaldoUsdt(), 1e-9);
        EstadoCartera estado = cartera.estado(110);
        assertEquals(bruto * (1 - C) - 500, estado.gananciaRealizada(), 1e-9);
        assertEquals(estado.gananciaRealizada(), estado.gananciaTotal(), 1e-9);
        assertEquals(0.5 + bruto * C, estado.comisionesPagadas(), 1e-9);
    }

    @Test
    void ventaParcialConservaElCostoPromedio() {
        Cartera cartera = new Cartera();
        cartera.comprar(1000, 100, 0);   // 10 BTC a 100
        cartera.vender(300, 150, 0);     // vende 2 BTC
        assertEquals(8, cartera.getBtc(), 1e-12);
        assertEquals(100, cartera.costoPromedio(), 1e-9);
        assertEquals(100, cartera.estado(150).gananciaRealizada(), 1e-9); // 300 − 2·100
        assertEquals(400, cartera.gananciaNoRealizada(150), 1e-9);        // 8·150 − 800
    }

    @Test
    void dosComprasPromedianElCosto() {
        Cartera cartera = new Cartera();
        cartera.comprar(1000, 100, 0); // 10 BTC
        cartera.comprar(1000, 200, 0); // 5 BTC
        assertEquals(15, cartera.getBtc(), 1e-12);
        assertEquals(2000.0 / 15, cartera.costoPromedio(), 1e-9);
    }

    @Test
    void rechazaCompraSinSaldoYVentaSinBtc() {
        Cartera cartera = new Cartera(1000);
        OperacionRechazadaException sinSaldo = assertThrows(OperacionRechazadaException.class,
                () -> cartera.comprar(1500, 100, C));
        assertEquals("Saldo insuficiente: la compra necesita 1500.00 USDT y hay 1000.00", sinSaldo.getMessage());
        assertThrows(OperacionRechazadaException.class, () -> cartera.vender(10, 100, C));
        assertThrows(OperacionRechazadaException.class, () -> cartera.venderTodo(100, C));
        assertEquals(1000, cartera.getSaldoUsdt()); // nada cambió
    }

    @Test
    void puedeGastarTodoElSaldoExacto() {
        Cartera cartera = new Cartera(1000);
        cartera.comprar(1000, 100, C);
        assertEquals(0, cartera.getSaldoUsdt());
        assertTrue(cartera.getBtc() > 0);
    }

    @Test
    void saldoInicialInvalido() {
        assertThrows(IllegalArgumentException.class, () -> new Cartera(0));
        assertThrows(IllegalArgumentException.class, () -> new Cartera(-5));
    }
}
