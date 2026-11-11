import dataclasses
import time

import pytest

from bitcoinai.ia.evaluacion import Metricas
from bitcoinai.ia.piloto import PilotoIA, consejo_para_usuario, decidir, intervalo_ia, volatilidad
from bitcoinai.ia.servicio import PrediccionIA, ServicioIA
from bitcoinai.modelo import Intervalo
from bitcoinai.simulacion import LimitesPiloto
from tests.apoyo.fuente_falsa import FuenteFalsa

LIMITES = LimitesPiloto(riesgo=0.2, stop_loss=0.05, take_profit=0.10)
FUTURO_S = time.time() + 10 * 365 * 86400  # todas las velas falsas ya cerraron


@pytest.fixture(scope="module")
def prediccion() -> PrediccionIA:
    return ServicioIA(FuenteFalsa(), "BTCUSDT", reloj=lambda: FUTURO_S).predecir(Intervalo.H1)


def con(prediccion: PrediccionIA, probabilidad: float, exactitud: float = 0.6, base: float = 0.5) -> PrediccionIA:
    metricas = Metricas(100, exactitud, base, 0.6, 50)
    comite = dataclasses.replace(prediccion.comite, probabilidad=probabilidad, metricas=metricas)
    return dataclasses.replace(prediccion, comite=comite)


def test_intervalo_y_volatilidad() -> None:
    assert intervalo_ia("1h") == "1h" and intervalo_ia("1m") == "15m"
    assert volatilidad((100.0, 100.0, 100.0)) == 0
    assert volatilidad((100.0, 101.0, 100.0, 101.0)) > 0
    assert volatilidad((100.0,)) == 0


@pytest.mark.parametrize(("probabilidad", "senal"), [(0.7, "COMPRAR"), (0.3, "VENDER"), (0.5, "MANTENER")])
def test_la_senal_sale_de_la_probabilidad(prediccion: PrediccionIA, probabilidad: float, senal: str) -> None:
    c = decidir(con(prediccion, probabilidad), 0.004, 100.0, LIMITES)
    assert c.senal == senal and c.precio == 100.0
    assert "comité" in c.motivo


def test_ajusta_el_riesgo_sin_pasar_los_topes(prediccion: PrediccionIA) -> None:
    seguro = decidir(con(prediccion, 0.9), 0.004, 100, LIMITES)
    dudoso = decidir(con(prediccion, 0.56), 0.004, 100, LIMITES)
    assert seguro.riesgo == pytest.approx(0.2) and dudoso.riesgo < seguro.riesgo
    # Si no le ganó a la base, arriesga la mitad.
    sin_ventaja = decidir(con(prediccion, 0.9, exactitud=0.45), 0.004, 100, LIMITES)
    assert sin_ventaja.riesgo == pytest.approx(0.1) and "la mitad" in sin_ventaja.motivo
    # Stop-loss = 3 × volatilidad (mínimo 1 %), take-profit = 2 × stop-loss, sin pasar los topes.
    assert (seguro.stop_loss, seguro.take_profit) == (pytest.approx(0.012), pytest.approx(0.024))
    agitado = decidir(con(prediccion, 0.9), 0.05, 100, LIMITES)
    assert (agitado.stop_loss, agitado.take_profit) == (0.05, 0.10)


def test_consejo_segun_la_cartera(prediccion: PrediccionIA) -> None:
    compra = decidir(con(prediccion, 0.7), 0.004, 100, LIMITES)
    assert consejo_para_usuario(compra, False)[0] == "COMPRAR"
    assert consejo_para_usuario(compra, True)[0] == "MANTENER"
    venta = decidir(con(prediccion, 0.3), 0.004, 100, LIMITES)
    assert consejo_para_usuario(venta, True)[:2] == ("VENDER", "La IA recomienda vender")
    assert consejo_para_usuario(venta, False)[0] == "ESPERAR"
    assert consejo_para_usuario(decidir(con(prediccion, 0.5), 0.004, 100, LIMITES), True)[0] == "ESPERAR"


def test_piloto_con_la_fuente() -> None:
    fuente = FuenteFalsa()
    piloto = PilotoIA(ServicioIA(fuente, "BTCUSDT", reloj=lambda: FUTURO_S), fuente, "BTCUSDT",
                      reloj=lambda: int(FUTURO_S * 1000))
    c = piloto.aconsejar("5m", LIMITES)
    assert c.intervalo == "15m" and c.senal in ("COMPRAR", "VENDER", "MANTENER")
    assert 0 < c.riesgo <= 0.2 and 0.01 <= c.stop_loss <= 0.05
