"""La memoria incremental da exactamente los mismos resultados que recalcular desde cero."""

import math

import pytest

from bitcoinai.estrategia import CruceDeMedias, Estrategia, EstrategiaCombinada, EstrategiaMacd, EstrategiaRsi
from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import Macd, Rsi, Sma, series
from bitcoinai.indicadores.incremental import EmaIncremental, MacdIncremental, RsiIncremental, SmaIncremental
from bitcoinai.modelo import Vela
from tests.estrategia.sinteticas import alcista_tras_caida, de_cierres, primeras


def serie_irregular(n: int = 300) -> ListaDoble[Vela]:
    """Precios que suben, bajan y oscilan, para ejercitar todos los cruces."""
    return de_cierres(*(80_000 + 4_000 * math.sin(i / 9) + 1_500 * math.cos(i / 4) + 25 * i for i in range(n)))


# ---------- calculadoras incrementales frente a los indicadores por lotes ----------


def test_sma_rsi_y_ema_incrementales_dan_los_mismos_valores() -> None:
    velas = serie_irregular()
    for incremental, lotes in ((SmaIncremental(20), Sma(20).calcular(velas)),
                               (RsiIncremental(14), Rsi(14).calcular(velas))):
        obtenidos = tuple(v for v in (incremental.agregar(vela.cierre) for vela in velas) if v is not None)
        assert obtenidos == tuple(p.valor for p in lotes)  # igualdad exacta, no aproximada
    ema = EmaIncremental(10)
    obtenidos = tuple(v for v in (ema.agregar(vela.cierre) for vela in velas) if v is not None)
    assert obtenidos == tuple(p.valor for p in series.ema(series.cierres(velas), 10))


def test_macd_incremental_da_los_mismos_valores() -> None:
    velas = serie_irregular()
    lotes = Macd(12, 26, 9).calcular_completo(velas)
    calculo = MacdIncremental(12, 26, 9)
    histogramas: tuple[float, ...] = ()
    for vela in velas:
        calculo.agregar(vela.cierre)
        if calculo.histograma is not None:
            histogramas += (calculo.histograma,)
    assert histogramas == tuple(p.valor for p in lotes.histograma)
    assert calculo.macd == lotes.macd.ultimo().valor
    assert calculo.senal == lotes.senal.ultimo().valor


# ---------- estrategias: lista que crece frente a prefijos nuevos ----------


@pytest.mark.parametrize("crear", [lambda: CruceDeMedias(5, 20), lambda: EstrategiaRsi(7), lambda: EstrategiaMacd(),
                                   lambda: EstrategiaCombinada()])
def test_evaluar_con_la_lista_creciendo_es_igual_que_recalcular_cada_prefijo(crear: object) -> None:
    velas = serie_irregular(200)
    incremental: Estrategia = crear()  # type: ignore[operator]
    creciente: ListaDoble[Vela] = ListaDoble()
    for n, vela in enumerate(velas, start=1):
        creciente.agregar_final(vela)
        rapida = incremental.evaluar(creciente)  # O(1): solo procesa la vela nueva
        nueva: Estrategia = crear()  # type: ignore[operator]
        desde_cero = nueva.evaluar(primeras(velas, n))  # O(n): estrategia y lista nuevas
        assert rapida == desde_cero, f"difiere en la vela {n - 1}"


def test_otra_lista_o_una_lista_modificada_recalcula_desde_cero() -> None:
    estrategia = CruceDeMedias(2, 4)
    velas = alcista_tras_caida()
    estrategia.evaluar(velas)
    # Misma estrategia, otra lista con datos distintos: debe dar lo mismo que una estrategia nueva.
    otra = de_cierres(10, 10, 10, 10, 10, 20)
    assert estrategia.evaluar(otra) == CruceDeMedias(2, 4).evaluar(otra)
    # La misma lista, modificada quitando la primera vela: también recalcula.
    otra.eliminar_primero()
    otra.agregar_final(otra.ultimo())
    assert estrategia.evaluar(otra) == CruceDeMedias(2, 4).evaluar(otra)


def test_evaluar_dos_veces_la_misma_lista_da_lo_mismo() -> None:
    estrategia = EstrategiaCombinada()
    velas = alcista_tras_caida()
    assert estrategia.evaluar(velas) == estrategia.evaluar(velas)
