package com.bitcoinai.backend;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.junit.jupiter.api.Test;

class MainTest {

    @Test
    void imprimeMensajeDeInicio() {
        PrintStream original = System.out;
        ByteArrayOutputStream salida = new ByteArrayOutputStream();
        System.setOut(new PrintStream(salida));
        try {
            Main.main(new String[0]);
        } finally {
            System.setOut(original);
        }
        assertEquals("Backend iniciado", salida.toString().trim());
    }
}
