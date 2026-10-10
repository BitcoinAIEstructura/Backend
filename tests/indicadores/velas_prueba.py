"""Utilidades para armar velas y comparar series en las pruebas de indicadores."""

import pytest

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import Serie
from bitcoinai.modelo import Vela

PASO = 60_000


def de_cierres(*cierres: float) -> ListaDoble[Vela]:
    """Velas planas (apertura = máximo = mínimo = cierre) en t = 0, 1 min, 2 min…"""
    velas: ListaDoble[Vela] = ListaDoble()
    for i, c in enumerate(cierres):
        velas.agregar_final(Vela(i * PASO, c, c, c, c, 1, i * PASO + PASO - 1))
    return velas


def constantes(n: int, valor: float) -> ListaDoble[Vela]:
    return de_cierres(*(valor for _ in range(n)))


def lineales(n: int, inicio: float, paso: float) -> ListaDoble[Vela]:
    return de_cierres(*(inicio + i * paso for i in range(n)))


def assert_serie(serie: Serie, primer_indice: int, *esperados: float) -> None:
    """Valores (con tolerancia) y que cada punto tenga el tiempo de la vela ``primer_indice + i``."""
    assert serie.tamanio() == len(esperados), "cantidad de puntos"
    for i, (punto, esperado) in enumerate(zip(serie, esperados, strict=True)):
        assert punto.valor == pytest.approx(esperado, abs=1e-9), f"valor del punto {i}"
        assert punto.tiempo == (primer_indice + i) * PASO, f"tiempo del punto {i}"


def assert_todos(serie: Serie, valor: float) -> None:
    for punto in serie:
        assert punto.valor == pytest.approx(valor, abs=1e-9)
