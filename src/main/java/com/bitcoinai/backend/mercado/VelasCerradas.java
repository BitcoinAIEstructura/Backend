package com.bitcoinai.backend.mercado;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Vela;

/**
 * Descarta la vela del periodo en curso, que todavía no cerró: sus valores aún
 * cambian, y una señal calculada con ella podría desaparecer al cerrar.
 */
public final class VelasCerradas {

    private VelasCerradas() {
    }

    /**
     * Quita del final las velas cuyo cierre no ha llegado.
     * Complejidad: O(k), con k velas quitadas (normalmente 0 o 1); cada
     * eliminarUltimo() de la ListaDoble es O(1).
     *
     * @param velas velas de la más antigua a la más reciente; se modifica
     * @param ahora momento actual en milisegundos
     * @return la misma lista, ya filtrada
     */
    public static ListaDoble<Vela> filtrar(ListaDoble<Vela> velas, long ahora) {
        while (!velas.estaVacia() && velas.ultimo().tiempoCierre() >= ahora) {
            velas.eliminarUltimo();
        }
        return velas;
    }
}
