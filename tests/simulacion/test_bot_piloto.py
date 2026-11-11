"""El bot en modo "Piloto IA", con un piloto falso que dice lo que se le pida."""

import pytest

from bitcoinai.modelo import Intervalo
from bitcoinai.simulacion import (
    BotSimulado,
    Cartera,
    ConfiguracionBot,
    ConsejoPiloto,
    EstadoOrden,
    LibroDeOrdenes,
    LimitesPiloto,
    OperacionInvalidaError,
    TipoEvento,
)
from tests.apoyo.fuente_falsa import FuenteFalsa, generar_velas
from tests.simulacion.estrategia_manual import EstrategiaManual


class PilotoFalso:
    def __init__(self) -> None:
        self.senal = "COMPRAR"
        self.limites: LimitesPiloto | None = None

    def aconsejar(self, intervalo: str, limites: LimitesPiloto) -> ConsejoPiloto:
        self.limites = limites
        return ConsejoPiloto(self.senal, 0.7, 0.4, 0.56, 0.51, 0.08, 0.02, 0.04, 0.005, "1h", 0, 100.0,
                             "El comité da 70 % de que sube.")


def armar(piloto: PilotoFalso | None) -> tuple[BotSimulado, LibroDeOrdenes, FuenteFalsa]:
    fuente = FuenteFalsa(generar_velas(300, Intervalo.H1), 100.0)
    libro = LibroDeOrdenes(Cartera(), fuente, "BTCUSDT")
    return BotSimulado(libro, fuente, EstrategiaManual(), "BTCUSDT", piloto=piloto), libro, fuente


def test_el_piloto_decide_y_elige_cuanto_arriesgar() -> None:
    piloto = PilotoFalso()
    bot, libro, fuente = armar(piloto)
    bot.iniciar(ConfiguracionBot(segundos_entre_ciclos=86_400, modo="ia"))
    bot.detener()
    bot.ejecutar_ciclo()
    compra = libro.ordenes(EstadoOrden.EJECUTADA).primero()
    assert compra.monto == pytest.approx(800)  # 8 % que eligió la IA, no el 20 % del tope
    assert compra.motivo.startswith("piloto IA: ")
    assert piloto.limites == LimitesPiloto(0.2, 0.05, 0.10)
    estado = bot.estado()
    assert estado.estrategia == "piloto-ia" and estado.piloto_disponible
    assert estado.ultimo_consejo is not None and estado.ultimo_consejo.riesgo == 0.08
    textos = [e.descripcion for e in libro.historial(20)]
    assert any(t.startswith("Piloto IA encendido") for t in textos)
    assert any(t.startswith("La IA decidió COMPRAR") for t in textos)


def test_el_stop_loss_del_piloto_usa_el_que_eligio_la_ia() -> None:
    piloto = PilotoFalso()
    bot, libro, fuente = armar(piloto)
    bot.iniciar(ConfiguracionBot(segundos_entre_ciclos=86_400, modo="ia"))
    bot.detener()
    bot.ejecutar_ciclo()
    # El precio cae 3 %: pasa el stop-loss de la IA (2 %) aunque no el tope (5 %).
    fuente.precio = 97.0
    piloto.senal = "MANTENER"
    bot.ejecutar_ciclo()
    venta = libro.ordenes(EstadoOrden.EJECUTADA).ultimo()
    assert venta.motivo.startswith("piloto IA · stop-loss")
    assert any(e.tipo is TipoEvento.STOP_LOSS for e in libro.historial(20))


def test_sin_piloto_no_se_puede_encender_el_modo_ia() -> None:
    bot, _, _ = armar(None)
    with pytest.raises(OperacionInvalidaError, match="piloto IA"):
        bot.iniciar(ConfiguracionBot(modo="ia"))
    with pytest.raises(ValueError, match="modo"):
        ConfiguracionBot(modo="magia")
