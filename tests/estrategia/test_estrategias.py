"""Señales esperadas de cada estrategia en tendencias sintéticas.

Alcista tras una caída (debe comprar después del giro), bajista tras una subida
(debe vender) y lateral (no debe hacer nada).
"""

import pytest

from bitcoinai.estrategia import CruceDeMedias, Estrategia, EstrategiaCombinada, EstrategiaMacd, EstrategiaRsi, Senal
from bitcoinai.estructuras import ListaDoble
from bitcoinai.modelo import Vela
from tests.estrategia.sinteticas import (
    DIA,
    GIRO,
    alcista_tras_caida,
    bajista_tras_subida,
    de_cierres,
    indice_de,
    lateral_plano,
    lateral_zigzag,
    senales,
)


def assert_una_senal_tras_el_giro(estrategia: Estrategia, velas: ListaDoble[Vela], esperada: Senal) -> None:
    encontradas = senales(estrategia, velas)
    assert len(encontradas) == 1, encontradas
    assert encontradas[0].startswith(esperada.name), encontradas
    assert indice_de(encontradas[0]) > GIRO, f"la señal debe llegar después del giro: {encontradas}"


# ---------- cruce de medias ----------


def test_cruce_compra_en_tendencia_alcista_y_vende_en_bajista() -> None:
    assert_una_senal_tras_el_giro(CruceDeMedias(5, 10), alcista_tras_caida(), Senal.COMPRAR)
    assert_una_senal_tras_el_giro(CruceDeMedias(5, 10), bajista_tras_subida(), Senal.VENDER)
    assert_una_senal_tras_el_giro(CruceDeMedias(), alcista_tras_caida(), Senal.COMPRAR)


def test_cruce_no_hace_nada_en_lateral_plano() -> None:
    assert senales(CruceDeMedias(5, 10), lateral_plano()) == ()


def test_cruce_explica_el_motivo_con_las_medias() -> None:
    decision = CruceDeMedias(2, 4).evaluar(de_cierres(10, 10, 10, 10, 10, 20))
    assert decision.senal is Senal.COMPRAR
    assert decision.motivo.startswith("Cruce alcista: la SMA 2 (15.00) cruzó por encima de la SMA 4 (12.50)")
    assert decision.confianza == 1.0  # separación del 12,5 % → confianza máxima
    assert decision.tiempo == 5 * DIA
    assert decision.precio == 20


# ---------- RSI ----------


def test_rsi_compra_al_salir_de_sobreventa_y_vende_al_salir_de_sobrecompra() -> None:
    assert_una_senal_tras_el_giro(EstrategiaRsi(), alcista_tras_caida(), Senal.COMPRAR)
    assert_una_senal_tras_el_giro(EstrategiaRsi(), bajista_tras_subida(), Senal.VENDER)


def test_rsi_compra_en_la_vela_exacta_calculada_a_mano() -> None:
    # Tras 45 velas con RSI 0, las subidas llevan el RSI a ~10, ~19, ~27 y ~34:
    # cruza 30 en la cuarta vela de subida (índice 63).
    assert senales(EstrategiaRsi(), alcista_tras_caida())[0] == "COMPRAR@63"


def test_rsi_no_hace_nada_en_lateral() -> None:
    assert senales(EstrategiaRsi(), lateral_plano()) == ()
    assert senales(EstrategiaRsi(), lateral_zigzag()) == ()


# ---------- MACD ----------


def test_macd_compra_tras_el_giro_alcista_y_vende_tras_el_bajista() -> None:
    assert_una_senal_tras_el_giro(EstrategiaMacd(), alcista_tras_caida(), Senal.COMPRAR)
    assert_una_senal_tras_el_giro(EstrategiaMacd(), bajista_tras_subida(), Senal.VENDER)


def test_macd_no_hace_nada_en_lateral_plano() -> None:
    assert senales(EstrategiaMacd(), lateral_plano()) == ()


# ---------- combinada ----------


def test_combinada_compra_en_alcista_sin_vender_y_vende_en_bajista_sin_comprar() -> None:
    alcista = senales(EstrategiaCombinada(), alcista_tras_caida())
    assert alcista and not any(s.startswith("VENDER") for s in alcista), alcista
    assert all(indice_de(s) > GIRO for s in alcista)
    bajista = senales(EstrategiaCombinada(), bajista_tras_subida())
    assert bajista and not any(s.startswith("COMPRAR") for s in bajista), bajista


def test_combinada_no_hace_nada_en_lateral_plano() -> None:
    assert senales(EstrategiaCombinada(), lateral_plano()) == ()


# ---------- casos generales ----------


@pytest.mark.parametrize("estrategia", [CruceDeMedias(), EstrategiaRsi(), EstrategiaMacd(), EstrategiaCombinada()])
def test_con_pocas_velas_todas_mantienen_con_confianza_cero(estrategia: Estrategia) -> None:
    decision = estrategia.evaluar(de_cierres(1, 2, 3))
    assert decision.senal is Senal.MANTENER
    assert decision.confianza == 0.0
    assert decision.motivo.startswith("Faltan velas")


def test_con_lista_vacia_o_nula_tambien_mantienen() -> None:
    assert CruceDeMedias().evaluar(ListaDoble()).senal is Senal.MANTENER
    assert EstrategiaCombinada().evaluar(None).senal is Senal.MANTENER


def test_velas_minimas_de_cada_estrategia() -> None:
    assert CruceDeMedias().velas_minimas() == 51
    assert EstrategiaRsi().velas_minimas() == 16
    assert EstrategiaMacd().velas_minimas() == 35
    assert EstrategiaCombinada().velas_minimas() == 51


def test_evaluar_no_modifica_las_velas() -> None:
    velas = alcista_tras_caida()
    EstrategiaCombinada().evaluar(velas)
    assert velas.tamanio() == 120


def test_indicadores_actuales_de_cada_estrategia() -> None:
    velas = alcista_tras_caida()
    assert tuple(CruceDeMedias().indicadores_actuales(velas)) == ("smaCorta", "smaLarga")
    assert tuple(EstrategiaRsi().indicadores_actuales(velas)) == ("rsi",)
    assert tuple(EstrategiaMacd().indicadores_actuales(velas)) == ("macd", "senalMacd", "histogramaMacd")
    assert len(EstrategiaCombinada().indicadores_actuales(velas)) == 6
    assert CruceDeMedias().indicadores_actuales(de_cierres(1)) == {}


def test_parametros_invalidos_en_los_constructores() -> None:
    for crear in (lambda: CruceDeMedias(50, 20), lambda: CruceDeMedias(0, 20), lambda: EstrategiaRsi(14, 60, 70),
                  lambda: EstrategiaRsi(0, 30, 70), lambda: EstrategiaMacd(26, 12, 9)):
        with pytest.raises(ValueError):
            crear()
