"""Índice de Fuerza Relativa (RSI)."""

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import series
from bitcoinai.indicadores.base import Indicador, PuntoIndicador, Serie
from bitcoinai.modelo import Vela


class Rsi(Indicador):
    """RSI con el suavizado de Wilder.

    Fórmula, con cambioₜ = cierreₜ − cierreₜ₋₁, gananciaₜ = max(cambioₜ, 0) y
    pérdidaₜ = max(−cambioₜ, 0):

    - Primeros promedios: media simple de las primeras p ganancias y pérdidas.
    - Después (Wilder): promedioₜ = (promedioₜ₋₁·(p − 1) + valorₜ) / p.
    - RS = promedioGanancias / promedioPérdidas; RSI = 100 − 100 / (1 + RS).

    Va de 0 a 100. El primer punto sale en la vela p (hacen falta p + 1 velas).

    Casos límite (decisión): sin pérdidas el RSI es 100; sin ganancias es 0; y
    sin ganancias ni pérdidas (serie plana) es **50**, porque no hay impulso hacia
    ningún lado. Así nunca se produce NaN, que además no se puede escribir en JSON.
    Complejidad: O(n), un recorrido hacia adelante; memoria extra O(1).
    """

    def __init__(self, periodo: int = 14) -> None:
        """Raises: ValueError si el periodo es menor que 1."""
        self.periodo = series.validar_periodo(periodo)

    def nombre(self) -> str:
        return "rsi"

    def parametros(self) -> dict[str, object]:
        return {"periodo": self.periodo}

    def calcular(self, velas: ListaDoble[Vela] | None) -> Serie:
        """Complejidad: O(n)."""
        resultado: Serie = ListaDoble()
        if velas is None:
            return resultado
        p = self.periodo
        anterior: Vela | None = None
        cambios = 0
        promedio_ganancia = 0.0
        promedio_perdida = 0.0
        for vela in velas:
            if anterior is not None:
                cambio = vela.cierre - anterior.cierre
                ganancia = max(cambio, 0.0)
                perdida = max(-cambio, 0.0)
                cambios += 1
                if cambios <= p:
                    # Durante el calentamiento se acumula para la media simple inicial.
                    promedio_ganancia += ganancia
                    promedio_perdida += perdida
                    if cambios == p:
                        promedio_ganancia /= p
                        promedio_perdida /= p
                        resultado.agregar_final(PuntoIndicador(vela.tiempo_apertura,
                                                               _rsi(promedio_ganancia, promedio_perdida)))
                else:
                    promedio_ganancia = (promedio_ganancia * (p - 1) + ganancia) / p
                    promedio_perdida = (promedio_perdida * (p - 1) + perdida) / p
                    resultado.agregar_final(PuntoIndicador(vela.tiempo_apertura,
                                                           _rsi(promedio_ganancia, promedio_perdida)))
            anterior = vela
        return resultado


def _rsi(promedio_ganancia: float, promedio_perdida: float) -> float:
    if promedio_perdida == 0:
        return 50.0 if promedio_ganancia == 0 else 100.0
    return 100.0 - 100.0 / (1.0 + promedio_ganancia / promedio_perdida)
