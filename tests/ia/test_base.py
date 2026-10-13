import pytest

from bitcoinai.estructuras import Lista
from bitcoinai.ia.base import Escalador, sigmoide
from bitcoinai.ia.caracteristicas import Muestra


def muestras(*vectores: tuple[float, ...]) -> Lista[Muestra]:
    lista: Lista[Muestra] = Lista()
    for i, v in enumerate(vectores):
        lista.agregar(Muestra(i, v, 0))
    return lista


def test_escalador_centra_y_divide_por_la_desviacion() -> None:
    e = Escalador()
    e.ajustar(muestras((0.0, 10.0), (2.0, 10.0), (4.0, 10.0)))
    assert e.media == pytest.approx((2.0, 10.0))
    x = e.transformar((4.0, 10.0))
    assert x[0] == pytest.approx(2 / (8 / 3) ** 0.5)
    assert x[1] == 0.0  # no varía: desviación 1, no se divide entre cero


def test_escalador_sin_muestras() -> None:
    with pytest.raises(ValueError, match="No hay muestras"):
        Escalador().ajustar(Lista())


def test_sigmoide_estable() -> None:
    assert sigmoide(0) == 0.5
    assert sigmoide(1000) == pytest.approx(1.0)
    assert sigmoide(-1000) == pytest.approx(0.0)
