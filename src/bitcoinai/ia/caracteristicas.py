"""De velas a ejemplos para aprender: características de cada vela y si la siguiente subió.

Cada característica usa solo la vela actual y las anteriores (nunca el futuro). La
etiqueta es lo único que mira adelante: 1 si la vela siguiente cerró más arriba.
Las velas se copian a ``Arreglo`` para leer "hace 5 velas" en O(1).
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from bitcoinai.estructuras import Arreglo, Lista
from bitcoinai.modelo import Vela

NOMBRES: tuple[str, ...] = (
    "Rendimiento de la última vela",
    "Rendimiento de 5 velas",
    "Rendimiento de 20 velas",
    "RSI 14",
    "Histograma del MACD",
    "Volatilidad de 20 velas",
    "Distancia a la SMA 20",
    "SMA 20 frente a SMA 50",
    "Volumen relativo",
    "Rango de la vela",
)
"""Nombre de cada característica, en el orden del vector."""

CALENTAMIENTO = 50
"""Velas necesarias antes de la primera muestra (la SMA 50 necesita 50)."""


@dataclass(frozen=True, slots=True)
class Muestra:
    """Un ejemplo: las características de una vela y qué pasó en la siguiente."""

    tiempo: int
    caracteristicas: tuple[float, ...]
    etiqueta: int  # 1 = la siguiente subió; 0 = no subió


class _Series:
    """Cierres, volúmenes, máximos y mínimos en arreglos, más los indicadores que se arrastran."""

    def __init__(self, velas: Iterable[Vela]) -> None:
        copia: Lista[Vela] = Lista()
        for v in velas:
            copia.agregar(v)
        n = copia.tamanio()
        self.n = n
        self.velas: Arreglo[Vela] = Arreglo(n)
        self.cierre: Arreglo[float] = Arreglo(n)
        self.volumen: Arreglo[float] = Arreglo(n)
        self.rsi: Arreglo[float] = Arreglo(n)
        self.histograma: Arreglo[float] = Arreglo(n)
        for i, v in enumerate(copia):
            self.velas.poner(i, v)
            self.cierre.poner(i, v.cierre)
            self.volumen.poner(i, v.volumen)
        self._calcular_rsi(14)
        self._calcular_macd(12, 26, 9)

    def c(self, i: int) -> float:
        valor = self.cierre.obtener(i)
        assert valor is not None
        return valor

    def _calcular_rsi(self, periodo: int) -> None:
        """RSI de Wilder, vela por vela: O(n)."""
        ganancia = perdida = 0.0
        for i in range(1, self.n):
            cambio = self.c(i) - self.c(i - 1)
            sube, baja = max(cambio, 0.0), max(-cambio, 0.0)
            if i <= periodo:
                ganancia += sube / periodo
                perdida += baja / periodo
            else:
                ganancia = (ganancia * (periodo - 1) + sube) / periodo
                perdida = (perdida * (periodo - 1) + baja) / periodo
            rsi = 100.0 if perdida == 0 else 100 - 100 / (1 + ganancia / perdida)
            self.rsi.poner(i, rsi)

    def _calcular_macd(self, rapido: int, lento: int, senal: int) -> None:
        """Histograma del MACD dividido entre el precio (así se compara en cualquier época). O(n)."""
        if self.n == 0:
            return
        k_r, k_l, k_s = 2 / (rapido + 1), 2 / (lento + 1), 2 / (senal + 1)
        ema_r = ema_l = self.c(0)
        ema_s = 0.0
        for i in range(self.n):
            ema_r += k_r * (self.c(i) - ema_r)
            ema_l += k_l * (self.c(i) - ema_l)
            macd = ema_r - ema_l
            ema_s += k_s * (macd - ema_s)
            self.histograma.poner(i, (macd - ema_s) / self.c(i))

    def media(self, arreglo: Arreglo[float], hasta: int, cuantas: int) -> float:
        """Promedio de las ``cuantas`` posiciones que terminan en ``hasta``. O(cuantas)."""
        suma = 0.0
        for j in range(hasta - cuantas + 1, hasta + 1):
            valor = arreglo.obtener(j)
            suma += 0.0 if valor is None else valor
        return suma / cuantas

    def caracteristicas(self, i: int) -> tuple[float, ...]:
        c = self.c
        rendimientos = Lista[float]()
        for j in range(i - 19, i + 1):
            rendimientos.agregar(c(j) / c(j - 1) - 1)
        promedio = sum(rendimientos) / 20
        volatilidad = math.sqrt(sum((r - promedio) ** 2 for r in rendimientos) / 20)
        sma20 = self.media(self.cierre, i, 20)
        sma50 = self.media(self.cierre, i, 50)
        volumen_medio = self.media(self.volumen, i, 20)
        vela = self.velas.obtener(i)
        assert vela is not None
        rsi = self.rsi.obtener(i)
        histograma = self.histograma.obtener(i)
        return (
            c(i) / c(i - 1) - 1,
            c(i) / c(i - 5) - 1,
            c(i) / c(i - 20) - 1,
            50.0 if rsi is None else rsi,
            0.0 if histograma is None else histograma,
            volatilidad,
            c(i) / sma20 - 1,
            sma20 / sma50 - 1,
            vela.volumen / volumen_medio - 1 if volumen_medio > 0 else 0.0,
            (vela.maximo - vela.minimo) / c(i),
        )


def construir_muestras(velas: Iterable[Vela]) -> tuple[Lista[Muestra], tuple[float, ...] | None, int | None]:
    """Las muestras de aprendizaje y las características de la última vela (para predecir).

    Returns:
        ``(muestras, ultima, tiempo_ultima)``. La última vela no tiene etiqueta (no se
        sabe qué viene), por eso va aparte. ``ultima`` es None si no hay velas suficientes.
    """
    s = _Series(velas)
    muestras: Lista[Muestra] = Lista()
    for i in range(CALENTAMIENTO, s.n - 1):
        vela = s.velas.obtener(i)
        assert vela is not None
        muestras.agregar(Muestra(vela.tiempo_apertura, s.caracteristicas(i), int(s.c(i + 1) > s.c(i))))
    if s.n <= CALENTAMIENTO:
        return muestras, None, None
    ultima = s.velas.obtener(s.n - 1)
    assert ultima is not None
    return muestras, s.caracteristicas(s.n - 1), ultima.tiempo_apertura
