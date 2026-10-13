"""Datos de prueba para los modelos: patrones que un modelo debería poder aprender."""

import random

from bitcoinai.estructuras import Lista
from bitcoinai.ia.base import Modelo
from bitcoinai.ia.caracteristicas import NOMBRES, Muestra


def separables(n: int = 400, semilla: int = 1) -> Lista[Muestra]:
    """Sube cuando el RSI (índice 3) está bajo 40: un patrón limpio y fácil de aprender."""
    azar = random.Random(semilla)
    lista: Lista[Muestra] = Lista()
    for i in range(n):
        x = tuple(azar.gauss(0, 1) for _ in NOMBRES)
        rsi = azar.uniform(10, 90)
        x = x[:3] + (rsi,) + x[4:]
        lista.agregar(Muestra(i, x, int(rsi < 40)))
    return lista


def ruido(n: int = 300, semilla: int = 2) -> Lista[Muestra]:
    """Etiquetas al azar: no hay nada que aprender."""
    azar = random.Random(semilla)
    lista: Lista[Muestra] = Lista()
    for i in range(n):
        lista.agregar(Muestra(i, tuple(azar.gauss(0, 1) for _ in NOMBRES), azar.randint(0, 1)))
    return lista


def vector(rsi: float) -> tuple[float, ...]:
    return (0.0, 0.0, 0.0, rsi) + (0.0,) * (len(NOMBRES) - 4)


def exactitud(modelo: Modelo, muestras: Lista[Muestra]) -> float:
    aciertos = sum(int((modelo.probabilidad(m.caracteristicas) >= 0.5) == bool(m.etiqueta)) for m in muestras)
    return aciertos / muestras.tamanio()
