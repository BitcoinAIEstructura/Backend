package com.bitcoinai.backend.mercado;

import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;

/**
 * Fuente de datos de mercado. Permite cambiar Binance por otra fuente (o por una
 * falsa en las pruebas) sin tocar el resto del backend.
 */
public interface FuenteDeMercado {

    /**
     * Obtiene las velas más recientes de un símbolo.
     *
     * @param simbolo   par de mercado, por ejemplo "BTCUSDT"
     * @param intervalo duración de cada vela
     * @param cantidad  número de velas a obtener (1 o más)
     * @return las velas ordenadas de la más antigua a la más reciente
     * @throws MercadoException si la fuente falla o entrega datos inválidos
     */
    ListaDoble<Vela> obtenerVelas(String simbolo, Intervalo intervalo, int cantidad);

    /**
     * Obtiene el último precio negociado de un símbolo.
     *
     * @param simbolo par de mercado, por ejemplo "BTCUSDT"
     * @return el precio actual
     * @throws MercadoException si la fuente falla o entrega datos inválidos
     */
    double obtenerPrecioActual(String simbolo);
}
