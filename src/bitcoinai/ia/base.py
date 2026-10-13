"""Lo común a los modelos: el escalador, la explicación y la interfaz ``Modelo``."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from bitcoinai.estructuras import Lista
from bitcoinai.ia.caracteristicas import Muestra

type Vector = tuple[float, ...]


class Escalador:
    """Pasa cada característica a "cuántas desviaciones se aleja del promedio".

    El RSI va de 0 a 100 y un rendimiento ronda 0,01: sin escalar, el RSI dominaría
    las distancias del k vecinos y los pasos de la regresión. La media y la
    desviación se aprenden SOLO con los datos de entrenamiento.
    """

    def __init__(self) -> None:
        self.media: Vector = ()
        self.desviacion: Vector = ()

    def ajustar(self, muestras: Iterable[Muestra]) -> None:
        """Calcula media y desviación de cada característica. O(n·d)."""
        sumas: Vector = ()
        cuadrados: Vector = ()
        n = 0
        for m in muestras:
            x = m.caracteristicas
            sumas = x if not sumas else tuple(a + b for a, b in zip(sumas, x, strict=True))
            cuadrados = (tuple(v * v for v in x) if not cuadrados
                         else tuple(a + b * b for a, b in zip(cuadrados, x, strict=True)))
            n += 1
        if n == 0:
            raise ValueError("No hay muestras para ajustar el escalador")
        self.media = tuple(s / n for s in sumas)
        # Desviación 1 si la característica no varía: así no se divide entre cero.
        self.desviacion = tuple(math.sqrt(max(q / n - mu * mu, 0.0)) or 1.0
                                for q, mu in zip(cuadrados, self.media, strict=True))

    def transformar(self, x: Vector) -> Vector:
        """O(d)."""
        return tuple((v - mu) / s for v, mu, s in zip(x, self.media, self.desviacion, strict=True))


@dataclass(frozen=True, slots=True)
class Explicacion:
    """Por qué el modelo decidió lo que decidió, en palabras y con pesos.

    ``factores``: (nombre de la característica, peso con signo). Positivo empuja a "sube".
    ``pasos``: frases en orden (las ramas del árbol, los vecinos más parecidos…).
    """

    resumen: str
    factores: tuple[tuple[str, float], ...]
    pasos: tuple[str, ...]


class Modelo(Protocol):
    """Interfaz de los modelos: se entrenan con muestras y dan la probabilidad de que suba."""

    nombre: str

    def entrenar(self, muestras: Lista[Muestra]) -> None: ...

    def probabilidad(self, x: Vector) -> float:
        """Probabilidad (0 a 1) de que la vela siguiente cierre más arriba."""
        ...

    def explicar(self, x: Vector) -> Explicacion: ...


def sigmoide(z: float) -> float:
    """1 / (1 + e^−z), estable para z muy grandes o muy chicos."""
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    e = math.exp(z)
    return e / (1 + e)
