package com.bitcoinai.backend.mercado;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertSame;

import java.io.IOException;
import org.junit.jupiter.api.Test;

class MercadoExceptionTest {

    @Test
    void guardaMensajeYCausa() {
        IOException causa = new IOException("red");
        MercadoException e = new MercadoException("Binance no responde", causa);
        assertInstanceOf(RuntimeException.class, e);
        assertEquals("Binance no responde", e.getMessage());
        assertSame(causa, e.getCause());
        assertEquals("solo mensaje", new MercadoException("solo mensaje").getMessage());
    }
}
