package com.bitcoinai.backend.mercado;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/**
 * Prueba manual contra la API real de Binance: necesita internet, por eso está
 * desactivada y {@code mvn test} no la ejecuta.
 *
 * <p>Para correrla a mano:
 * <pre>
 * mvn test -Dtest=ClienteBinanceManualTest -Djunit.jupiter.conditions.deactivate=org.junit.*DisabledCondition
 * </pre>
 * Si Binance está bloqueado en tu país, define antes BINANCE_BASE_URL
 * (por ejemplo https://data-api.binance.vision).
 */
@Disabled("Prueba manual: necesita internet")
@Tag("manual")
class ClienteBinanceManualTest {

    @Test
    void descargaDiezVelasDiariasRealesDeBtcUsdt() {
        ClienteBinance cliente = new ClienteBinance();
        ListaDoble<Vela> velas = cliente.obtenerVelas("BTCUSDT", Intervalo.D1, 10);

        System.out.println("URL base: " + cliente.getUrlBase());
        System.out.println("Fecha (UTC)   Apertura      Máximo        Mínimo        Cierre        Volumen");
        for (Vela v : velas) {
            System.out.printf("%s  %-12.2f  %-12.2f  %-12.2f  %-12.2f  %.2f%n",
                    Instant.ofEpochMilli(v.tiempoApertura()).atZone(ZoneOffset.UTC).toLocalDate(),
                    v.apertura(), v.maximo(), v.minimo(), v.cierre(), v.volumen());
        }
        double precio = cliente.obtenerPrecioActual("BTCUSDT");
        System.out.printf("Precio actual BTCUSDT: %.2f%n", precio);

        assertEquals(10, velas.tamanio());
        assertTrue(precio > 0);
    }
}
