import pytest

from bitcoinai.estructuras import Lista
from bitcoinai.ia.caracteristicas import Muestra
from bitcoinai.ia.vecinos import KVecinos
from tests.ia.apoyo import exactitud, separables, vector


def test_aprende_un_patron_limpio() -> None:
    modelo = KVecinos(k=15)
    modelo.entrenar(separables())
    assert exactitud(modelo, separables(n=150, semilla=9)) > 0.75
    assert modelo.probabilidad(vector(15)) > 0.5


def test_elige_los_k_mas_cercanos_en_orden() -> None:
    muestras: Lista[Muestra] = Lista()
    for i in range(10):
        muestras.agregar(Muestra(i * 1000, vector(float(i)), int(i < 5)))
    modelo = KVecinos(k=3)
    modelo.entrenar(muestras)
    elegidos = tuple(modelo.vecinos(vector(7.2)))
    assert tuple(t for _, _, t in elegidos) == (7000, 8000, 6000)
    assert elegidos[0][0] <= elegidos[1][0] <= elegidos[2][0]
    assert modelo.probabilidad(vector(7.2)) == pytest.approx(1 / 5)  # 0 de 3 subieron, con Laplace


def test_explica_con_las_fechas_de_los_parecidos() -> None:
    modelo = KVecinos(k=5)
    modelo.entrenar(separables())
    e = modelo.explicar(vector(20))
    assert e.resumen.startswith("De las 5 velas del pasado más parecidas a esta")
    assert len(e.pasos) == 4 and "UTC (distancia" in e.pasos[1]


def test_sin_entrenar() -> None:
    with pytest.raises(ValueError, match="no está entrenado"):
        KVecinos().probabilidad(vector(1))
