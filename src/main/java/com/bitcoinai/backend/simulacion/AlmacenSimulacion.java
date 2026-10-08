package com.bitcoinai.backend.simulacion;

import java.util.Optional;

/**
 * Dónde se guarda el estado de la simulación. El libro de órdenes solo conoce
 * esta interfaz; la implementación con archivos JSON está en el paquete
 * {@code persistencia}.
 */
public interface AlmacenSimulacion {

    /**
     * Guarda el estado completo.
     *
     * @param estado foto del libro de órdenes
     * @throws RuntimeException si no se pudo guardar (el libro lo registra y sigue)
     */
    void guardar(EstadoSimulacion estado);

    /**
     * Carga el último estado guardado. Si no hay nada o está dañado, devuelve
     * vacío (y registra una advertencia si estaba dañado), nunca falla.
     *
     * @return el estado, o vacío para empezar limpio
     */
    Optional<EstadoSimulacion> cargar();
}
