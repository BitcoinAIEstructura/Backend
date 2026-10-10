"""Máxima caída (drawdown máximo)."""

from dataclasses import dataclass

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import series
from bitcoinai.indicadores.base import Serie
from bitcoinai.modelo import Vela


@dataclass(frozen=True, slots=True)
class ResultadoCaida:
    """Resultado de la máxima caída.

    Si la serie está vacía todos los campos son 0. Si nunca baja, la caída es 0 y
    el pico y el valle son el primer punto.

    Atributos:
        caida_maxima: fracción entre 0 y 1 (0,25 = cayó un 25 % desde el pico).
        tiempo_pico: momento del pico previo a la peor caída.
        valor_pico: valor en el pico.
        tiempo_valle: momento del punto más bajo de esa caída.
        valor_valle: valor en el valle.
    """

    caida_maxima: float
    tiempo_pico: int
    valor_pico: float
    tiempo_valle: int
    valor_valle: float


def maxima_caida_de_velas(velas: ListaDoble[Vela] | None) -> ResultadoCaida:
    """Máxima caída de los cierres de una serie de velas. Complejidad: O(n)."""
    return maxima_caida_de_puntos(series.cierres(velas))


def maxima_caida_de_puntos(serie: Serie | None) -> ResultadoCaida:
    """La mayor bajada porcentual desde un pico hasta un punto posterior.

    Fórmula: caídaₜ = (picoₜ − xₜ) / picoₜ, donde picoₜ es el máximo visto hasta t;
    el resultado es el mayor caídaₜ.

    Se recorre la serie **una sola vez** hacia adelante, llevando el pico máximo
    visto hasta el momento: O(n) en tiempo y O(1) en memoria extra. También sirve
    para la curva de capital del backtest, por eso acepta puntos.
    """
    if serie is None or serie.esta_vacia():
        return ResultadoCaida(0.0, 0, 0.0, 0, 0.0)
    pico = serie.primero()
    peor = ResultadoCaida(0.0, pico.tiempo, pico.valor, pico.tiempo, pico.valor)
    for punto in serie:
        if punto.valor > pico.valor:
            pico = punto
        caida = (pico.valor - punto.valor) / pico.valor
        if caida > peor.caida_maxima:
            peor = ResultadoCaida(caida, pico.tiempo, pico.valor, punto.tiempo, punto.valor)
    return peor
