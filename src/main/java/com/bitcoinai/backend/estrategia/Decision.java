package com.bitcoinai.backend.estrategia;

import java.util.Objects;

/**
 * Decisión de una estrategia en una vela.
 *
 * @param tiempo    tiempo de apertura de la vela en que se decidió
 * @param senal     qué hacer
 * @param precio    cierre de esa vela
 * @param confianza entre 0 y 1
 * @param motivo    una frase en español que explica por qué
 */
public record Decision(long tiempo, Senal senal, double precio, double confianza, String motivo) {

    /**
     * Valida los campos.
     *
     * @throws IllegalArgumentException si la confianza no está entre 0 y 1 o el motivo está vacío
     */
    public Decision {
        Objects.requireNonNull(senal, "senal");
        if (motivo == null || motivo.isBlank()) {
            throw new IllegalArgumentException("La decisión necesita un motivo");
        }
        if (!(confianza >= 0 && confianza <= 1)) {
            throw new IllegalArgumentException("La confianza debe estar entre 0 y 1: " + confianza);
        }
    }
}
