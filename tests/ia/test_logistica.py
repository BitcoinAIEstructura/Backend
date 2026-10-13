from bitcoinai.ia.base import por_peso
from bitcoinai.ia.logistica import RegresionLogistica
from tests.ia.apoyo import exactitud, separables, vector


def test_aprende_un_patron_limpio() -> None:
    modelo = RegresionLogistica()
    modelo.entrenar(separables())
    assert exactitud(modelo, separables(semilla=9)) > 0.9
    assert modelo.probabilidad(vector(20)) > 0.8
    assert modelo.probabilidad(vector(80)) < 0.2


def test_explica_que_el_rsi_es_lo_que_mas_pesa() -> None:
    modelo = RegresionLogistica()
    modelo.entrenar(separables())
    e = modelo.explicar(vector(20))
    assert e.factores[0][0] == "RSI 14"
    assert e.factores[0][1] > 0  # RSI bajo empuja a subir
    assert "RSI 14" in e.resumen and "subir" in e.resumen
    assert len(e.pasos) == 4


def test_por_peso_ordena_por_valor_absoluto() -> None:
    assert por_peso((("a", 0.1), ("b", -0.9), ("c", 0.5))) == (("b", -0.9), ("c", 0.5), ("a", 0.1))
