import pytest

from bitcoinai.estructuras import Lista
from bitcoinai.ia.arbol import ArbolDecision
from bitcoinai.ia.base import Explicacion, Vector
from bitcoinai.ia.caracteristicas import Muestra
from bitcoinai.ia.comite import Comite
from bitcoinai.ia.evaluacion import dividir_en_el_tiempo, evaluar
from bitcoinai.ia.logistica import RegresionLogistica
from tests.ia.apoyo import exactitud, ruido, separables, vector


class Fijo:
    """Modelo que siempre dice la misma probabilidad."""

    def __init__(self, p: float, nombre: str = "Fijo") -> None:
        self.p, self.nombre = p, nombre

    def entrenar(self, muestras: Lista[Muestra]) -> None:
        pass

    def probabilidad(self, x: Vector) -> float:
        return self.p

    def explicar(self, x: Vector) -> Explicacion:
        return Explicacion("", (), ())


def test_divide_en_orden_sin_mezclar() -> None:
    muestras = separables(10)
    entrenamiento, prueba = dividir_en_el_tiempo(muestras, 0.3)
    assert tuple(m.tiempo for m in entrenamiento) == tuple(range(7))
    assert tuple(m.tiempo for m in prueba) == (7, 8, 9)
    with pytest.raises(ValueError):
        dividir_en_el_tiempo(muestras, 1.0)


def test_metricas_y_base() -> None:
    prueba: Lista[Muestra] = Lista()
    for i, etiqueta in enumerate((1, 1, 1, 0)):
        prueba.agregar(Muestra(i, vector(0), etiqueta))
    siempre_sube = evaluar(Fijo(0.9), prueba)
    assert (siempre_sube.exactitud, siempre_sube.base, siempre_sube.ventaja) == (0.75, 0.75, 0.0)
    assert (siempre_sube.precision_sube, siempre_sube.veces_dijo_sube) == (0.75, 4)
    nunca = evaluar(Fijo(0.1), prueba)
    assert nunca.precision_sube is None and nunca.exactitud == 0.25
    with pytest.raises(ValueError):
        evaluar(Fijo(0.5), Lista())


def test_en_ruido_ningun_modelo_le_gana_de_verdad_a_la_base() -> None:
    entrenamiento, prueba = dividir_en_el_tiempo(ruido(1000), 0.3)
    modelo = RegresionLogistica(epocas=100)
    modelo.entrenar(entrenamiento)
    assert evaluar(modelo, prueba).ventaja < 0.08


def test_el_comite_pesa_mas_al_que_sabe() -> None:
    comite = Comite((lambda: RegresionLogistica(epocas=150), lambda: Fijo(0.5, "Azar")))
    comite.entrenar(separables(500))
    assert comite.pesos[0] > 0.8 > comite.pesos[1]
    assert sum(comite.pesos) == pytest.approx(1.0)
    assert exactitud(comite, separables(200, semilla=8)) > 0.9
    e = comite.explicar(vector(20))
    assert e.resumen == "2 de 2 modelos creen que sube; el que más empuja es Regresión logística, hacia subir."
    assert e.pasos[1].startswith("Azar: 50 % de que suba")


def test_si_nadie_supera_la_base_pesan_igual() -> None:
    comite = Comite((lambda: Fijo(0.5, "A"), lambda: ArbolDecision(profundidad_maxima=0)))
    comite.entrenar(separables(200))
    assert comite.pesos == pytest.approx((0.5, 0.5))


def test_comite_sin_entrenar() -> None:
    with pytest.raises(ValueError, match="no está entrenado"):
        Comite((lambda: Fijo(0.5),)).probabilidad(vector(1))


def test_textos_del_veredicto_y_la_conclusion() -> None:
    from bitcoinai.ia.evaluacion import Metricas
    from bitcoinai.ia.textos import conclusion_externos, nombre_intervalo, veredicto

    gana = Metricas(muestras=200, exactitud=0.55, base=0.52, precision_sube=0.6, veces_dijo_sube=100)
    pierde = Metricas(muestras=200, exactitud=0.5, base=0.52, precision_sube=0.5, veces_dijo_sube=90)
    v = veredicto(gana)
    assert v.gana and "55,0 %" in v.texto and "+3,0 puntos" in v.texto
    assert not veredicto(pierde).gana and "experimento" in veredicto(pierde).texto
    assert "acertó más" in conclusion_externos(pierde, gana)
    assert "acertó menos" in conclusion_externos(gana, pierde) and "ruido" in conclusion_externos(gana, pierde)
    assert "casi lo mismo" in conclusion_externos(gana, gana)
    assert nombre_intervalo("4h") == "4 h" and nombre_intervalo("2h") == "2h"
