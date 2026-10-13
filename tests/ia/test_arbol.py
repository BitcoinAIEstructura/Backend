import pytest

from bitcoinai.estructuras import Lista
from bitcoinai.ia.arbol import ArbolDecision, NodoDecision
from bitcoinai.ia.caracteristicas import Muestra
from tests.ia.apoyo import exactitud, ruido, separables, vector


def test_encuentra_el_corte_del_rsi() -> None:
    arbol = ArbolDecision()
    arbol.entrenar(separables())
    assert arbol.raiz is not None and arbol.raiz.caracteristica == 3  # la primera pregunta es el RSI
    assert arbol.raiz.umbral == pytest.approx(40, abs=6)
    assert exactitud(arbol, separables(semilla=9)) > 0.9


def test_explica_el_camino() -> None:
    arbol = ArbolDecision()
    arbol.entrenar(separables())
    e = arbol.explicar(vector(20))
    assert e.pasos[0].startswith("¿RSI 14 ≤")
    assert e.pasos[0].endswith("sí.")
    assert "subió el" in e.resumen
    assert e.factores[0][0] == "RSI 14"
    assert sum(p for _, p in e.factores) == pytest.approx(1.0)


def test_no_pasa_de_la_profundidad_maxima_ni_deja_hojas_chicas() -> None:
    arbol = ArbolDecision(profundidad_maxima=3, minimo_hoja=25)
    arbol.entrenar(ruido(600))
    assert arbol.profundidad() <= 3

    def revisar(nodo: NodoDecision | None) -> None:
        assert nodo is not None and nodo.muestras >= 25
        if not nodo.es_hoja:
            revisar(nodo.si)
            revisar(nodo.no)
    revisar(arbol.raiz)


def test_si_todas_suben_es_una_sola_hoja() -> None:
    muestras: Lista[Muestra] = Lista()
    for i in range(50):
        muestras.agregar(Muestra(i, vector(i), 1))
    arbol = ArbolDecision()
    arbol.entrenar(muestras)
    assert arbol.raiz is not None and arbol.raiz.es_hoja
    assert arbol.probabilidad(vector(10)) == pytest.approx(51 / 52)


def test_sin_entrenar_o_sin_datos() -> None:
    with pytest.raises(ValueError, match="no está entrenado"):
        ArbolDecision().probabilidad(vector(1))
    with pytest.raises(ValueError, match="No hay muestras"):
        ArbolDecision().entrenar(Lista())
