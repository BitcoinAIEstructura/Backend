package com.bitcoinai.backend.simulacion;

import com.bitcoinai.backend.estructuras.Lista;

/**
 * Foto completa del libro de órdenes, para guardarla y reconstruirla. Las listas
 * van en el orden en que hay que volver a cargarlas.
 *
 * @param cartera     datos de la cartera, o null si no había (se usa una nueva)
 * @param siguienteId próximo id de orden
 * @param pendientes  órdenes pendientes en orden de cola (la primera es el frente)
 * @param registro    órdenes terminadas, en el orden en que terminaron
 * @param creadas     ids en orden de creación, del más viejo al más nuevo (el último es el tope de la pila)
 * @param eventos     historial del más viejo al más nuevo (el último es el tope de la pila)
 */
public record EstadoSimulacion(
        DatosCartera cartera,
        long siguienteId,
        Lista<Orden> pendientes,
        Lista<Orden> registro,
        Lista<Long> creadas,
        Lista<Evento> eventos) {
}
