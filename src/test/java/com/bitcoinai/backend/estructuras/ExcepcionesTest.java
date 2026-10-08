package com.bitcoinai.backend.estructuras;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;

import org.junit.jupiter.api.Test;

class ExcepcionesTest {

    @Test
    void estructuraVaciaEsRuntimeExceptionConMensaje() {
        EstructuraVaciaException e = new EstructuraVaciaException("La cola está vacía");
        assertInstanceOf(RuntimeException.class, e);
        assertEquals("La cola está vacía", e.getMessage());
    }

    @Test
    void indiceFueraDeRangoIndicaIndiceYTamanio() {
        IndiceFueraDeRangoException e = new IndiceFueraDeRangoException(5, 3);
        assertInstanceOf(RuntimeException.class, e);
        assertEquals("Índice 5 fuera de rango para tamaño 3", e.getMessage());
    }
}
