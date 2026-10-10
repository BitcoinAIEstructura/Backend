"""Volatilidad de los retornos logarítmicos."""

import math

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import series
from bitcoinai.indicadores.base import Indicador, PuntoIndicador, Serie
from bitcoinai.modelo import Vela


class Volatilidad(Indicador):
    """Desviación estándar de los retornos logarítmicos en una ventana.

    Fórmula: rₜ = ln(cierreₜ / cierreₜ₋₁). Sobre los últimos p retornos,
    σ = √((Σr² − (Σr)²/p) / (p − 1)) (desviación muestral, porque estima la
    volatilidad a partir de una muestra). No está anualizada: es la volatilidad por
    vela (con velas diarias, multiplicar por √365 da la anual). El primer punto
    sale en la vela p (hacen falta p + 1 cierres para p retornos).

    Usa una ventana ListaDoble con suma y suma de cuadrados acumuladas:
    O(n) en total, O(p) de memoria extra.
    """

    def __init__(self, periodo: int = 20) -> None:
        """Raises: ValueError si el periodo es menor que 2 (por la división entre p − 1)."""
        self.periodo = series.validar_periodo(periodo, minimo=2)

    def nombre(self) -> str:
        return "volatilidad"

    def parametros(self) -> dict[str, object]:
        return {"periodo": self.periodo}

    def calcular(self, velas: ListaDoble[Vela] | None) -> Serie:
        """Complejidad: O(n) en tiempo, O(p) en memoria extra."""
        resultado: Serie = ListaDoble()
        if velas is None:
            return resultado
        p = self.periodo
        ventana: ListaDoble[float] = ListaDoble()
        suma = 0.0
        suma_cuadrados = 0.0
        anterior: Vela | None = None
        for vela in velas:
            if anterior is not None:
                retorno = math.log(vela.cierre / anterior.cierre)
                ventana.agregar_final(retorno)
                suma += retorno
                suma_cuadrados += retorno * retorno
                if ventana.tamanio() > p:
                    viejo = ventana.primero()
                    suma -= viejo
                    suma_cuadrados -= viejo * viejo
                    ventana.conservar_ultimos(p)
                if ventana.tamanio() == p:
                    varianza = max(0.0, (suma_cuadrados - suma * suma / p) / (p - 1))
                    resultado.agregar_final(PuntoIndicador(vela.tiempo_apertura, math.sqrt(varianza)))
            anterior = vela
        return resultado
