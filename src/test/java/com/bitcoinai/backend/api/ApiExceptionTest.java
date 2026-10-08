package com.bitcoinai.backend.api;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class ApiExceptionTest {

    @Test
    void guardaCodigoYMensaje() {
        ApiException e = new ApiException(400, "Parámetro inválido");
        assertEquals(400, e.getCodigo());
        assertEquals("Parámetro inválido", e.getMessage());
        assertEquals(200, Respuesta.ok("x").codigo());
    }
}
