import math

import pytest

from bitcoinai.estrategia import (
    AVISO,
    Componente,
    Decision,
    Direccion,
    EstrategiaCombinada,
    EstrategiaRsi,
    Pronostico,
    Senal,
    direccion_de,
)
from tests.estrategia.sinteticas import EstrategiaGuion, alcista_tras_caida, de_cierres, lateral_plano, primeras

VELAS = de_cierres(100, 101, 102)


def fija(nombre: str, senal: Senal, confianza: float = 0.8) -> EstrategiaGuion:
    return EstrategiaGuion(nombre, senal, confianza)


def combinar(*pares: tuple[EstrategiaGuion, float]) -> EstrategiaCombinada:
    return EstrategiaCombinada(Componente(e, peso) for e, peso in pares)


# ---------- votación ponderada ----------


def test_gana_la_senal_con_mayor_puntaje_ponderado() -> None:
    # COMPRAR 0,8·1, VENDER 0,6·1, MANTENER 0,25·1 → puntajes /3: 0,267 / 0,2 / 0,083
    c = combinar((fija("a", Senal.COMPRAR, 0.8), 1), (fija("b", Senal.VENDER, 0.6), 1), (fija("c", Senal.MANTENER), 1))
    d = c.evaluar(VELAS)
    assert d.senal is Senal.COMPRAR
    assert d.confianza == pytest.approx(0.8 / 3)
    assert d.motivo == "Votación ponderada: COMPRAR 0.27, VENDER 0.20, MANTENER 0.08; gana COMPRAR."


def test_los_pesos_cambian_el_resultado() -> None:
    # Con peso 0 para quien compra: VENDER 0,6/2 = 0,3 frente a MANTENER 0,25/2 = 0,125
    c = combinar((fija("a", Senal.COMPRAR, 0.8), 0), (fija("b", Senal.VENDER, 0.6), 1), (fija("c", Senal.MANTENER), 1))
    d = c.evaluar(VELAS)
    assert d.senal is Senal.VENDER
    assert d.confianza == pytest.approx(0.3)


def test_dos_que_mantienen_le_ganan_a_una_senal_debil() -> None:
    c = combinar((fija("a", Senal.COMPRAR, 0.4), 1), (fija("b", Senal.MANTENER), 1), (fija("c", Senal.MANTENER), 1))
    assert c.evaluar(VELAS).senal is Senal.MANTENER


def test_si_comprar_y_vender_empatan_se_mantiene() -> None:
    d = combinar((fija("a", Senal.COMPRAR, 0.7), 1), (fija("b", Senal.VENDER, 0.7), 1)).evaluar(VELAS)
    assert d.senal is Senal.MANTENER
    assert "se contradicen" in d.motivo


def test_pesos_invalidos() -> None:
    with pytest.raises(ValueError):
        combinar((fija("a", Senal.COMPRAR), 0))
    with pytest.raises(ValueError):
        combinar((fija("a", Senal.COMPRAR), -1))
    with pytest.raises(ValueError):
        EstrategiaCombinada(())
    with pytest.raises(ValueError):
        EstrategiaCombinada.con_pesos(0, 0, 0)


def test_parametros_muestran_pesos_y_estrategias() -> None:
    assert EstrategiaCombinada.con_pesos(2, 1, 0.5).parametros() == {
        "pesos": {"cruce": 2, "rsi": 1, "macd": 0.5},
        "estrategias": {"cruce": {"corta": 20, "larga": 50},
                        "rsi": {"periodo": 14, "sobreventa": 30.0, "sobrecompra": 70.0},
                        "macd": {"rapido": 12, "lento": 26, "senal": 9}},
    }


# ---------- pronóstico ----------


def test_direccion_segun_la_senal() -> None:
    assert direccion_de(Senal.COMPRAR) is Direccion.SUBE
    assert direccion_de(Senal.VENDER) is Direccion.BAJA
    assert direccion_de(Senal.MANTENER) is Direccion.LATERAL


def test_pronostico_de_la_combinada_se_justifica_con_las_que_votaron_lo_mismo() -> None:
    c = combinar((fija("a", Senal.COMPRAR, 0.9), 1), (fija("b", Senal.COMPRAR, 0.7), 1),
                 (fija("c", Senal.VENDER, 0.6), 1))
    d = c.evaluar(VELAS)
    p = Pronostico.desde(c, VELAS, d)
    assert p.direccion is Direccion.SUBE
    assert p.confianza == d.confianza
    assert tuple(p.justificacion) == ("a: a dice COMPRAR en la vela 2.", "b: b dice COMPRAR en la vela 2.")
    assert p.indicadores == {"a": 1.0, "b": 1.0, "c": 1.0}
    assert p.aviso == "Resultado de pruebas con datos históricos; no es asesoría financiera ni garantiza ganancias"
    assert p.aviso == AVISO


def test_pronostico_real_tras_un_giro_alcista() -> None:
    # En la vela 63 el RSI sale de sobreventa: la combinada compra.
    velas = primeras(alcista_tras_caida(), 64)
    combinada = EstrategiaCombinada()
    d = combinada.evaluar(velas)
    p = Pronostico.desde(combinada, velas, d)
    assert p.direccion is Direccion.SUBE
    assert p.justificacion.primero().startswith("rsi: El RSI salió de sobreventa")
    assert "rsi" in p.indicadores and "smaLarga" in p.indicadores


def test_pronostico_de_una_estrategia_simple_usa_su_motivo() -> None:
    rsi = EstrategiaRsi()
    velas = lateral_plano()
    d = rsi.evaluar(velas)
    p = Pronostico.desde(rsi, velas, d)
    assert p.direccion is Direccion.LATERAL
    assert p.justificacion.primero() == d.motivo
    assert p.indicadores["rsi"] == 50.0


# ---------- decisión ----------


@pytest.mark.parametrize(("confianza", "motivo"), [(1.5, "x"), (-0.1, "x"), (math.nan, "x"), (0.5, " ")])
def test_decision_valida_confianza_y_motivo(confianza: float, motivo: str) -> None:
    with pytest.raises(ValueError):
        Decision(0, Senal.COMPRAR, 1, confianza, motivo)
