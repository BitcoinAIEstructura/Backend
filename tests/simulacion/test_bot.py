import time
from collections.abc import Iterator

import pytest

from bitcoinai.estrategia import Decision, Senal
from bitcoinai.estructuras import ListaDoble
from bitcoinai.mercado import MercadoError
from bitcoinai.modelo import Intervalo, Vela
from bitcoinai.simulacion import (
    BotSimulado,
    Cartera,
    ConfiguracionBot,
    EstadoCartera,
    EstadoOrden,
    LibroDeOrdenes,
    OperacionInvalidaError,
    Orden,
    TipoEvento,
    TipoOrden,
)
from tests.apoyo.fuente_falsa import FuenteFalsa, generar_velas
from tests.simulacion.estrategia_manual import EstrategiaManual


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa(generar_velas(300, Intervalo.H1), 100.0)


@pytest.fixture
def libro(fuente: FuenteFalsa) -> LibroDeOrdenes:
    return LibroDeOrdenes(Cartera(), fuente, "BTCUSDT")


@pytest.fixture
def estrategia() -> EstrategiaManual:
    return EstrategiaManual()


@pytest.fixture
def bot(libro: LibroDeOrdenes, fuente: FuenteFalsa, estrategia: EstrategiaManual) -> Iterator[BotSimulado]:
    bot = BotSimulado(libro, fuente, estrategia, "BTCUSDT")
    yield bot
    bot.detener()


def cartera(libro: LibroDeOrdenes, precio: float = 100) -> EstadoCartera:
    return libro.estado_cartera(precio)


def hay_evento(libro: LibroDeOrdenes, tipo: TipoEvento) -> bool:
    return any(e.tipo is tipo for e in libro.historial(100))


def ultima_ejecutada(libro: LibroDeOrdenes) -> Orden:
    return libro.ordenes(EstadoOrden.EJECUTADA).ultimo()


# ---------- decisiones ----------


def test_con_comprar_y_sin_posicion_compra_el_veinte_por_ciento_del_saldo(
        bot: BotSimulado, libro: LibroDeOrdenes, estrategia: EstrategiaManual) -> None:
    estrategia.decir(Senal.COMPRAR)
    bot.ejecutar_ciclo()
    ejecutadas = libro.ordenes(EstadoOrden.EJECUTADA)
    assert ejecutadas.tamanio() == 1
    compra = ejecutadas.primero()
    assert compra.tipo is TipoOrden.COMPRA
    assert compra.monto == pytest.approx(2_000)
    assert compra.motivo.startswith("señal del bot: ")
    assert cartera(libro).saldo_usdt == pytest.approx(8_000)
    assert cartera(libro).btc > 0


def test_con_comprar_y_con_posicion_no_compra_otra_vez(bot: BotSimulado, libro: LibroDeOrdenes,
                                                      estrategia: EstrategiaManual) -> None:
    estrategia.decir(Senal.COMPRAR)
    bot.ejecutar_ciclo()
    bot.ejecutar_ciclo()
    assert libro.ordenes().tamanio() == 1


def test_con_vender_y_con_posicion_vende_todo(bot: BotSimulado, libro: LibroDeOrdenes,
                                             estrategia: EstrategiaManual) -> None:
    estrategia.decir(Senal.COMPRAR)
    bot.ejecutar_ciclo()
    estrategia.decir(Senal.VENDER)
    bot.ejecutar_ciclo()
    venta = ultima_ejecutada(libro)
    assert venta.tipo is TipoOrden.VENTA and venta.todo
    assert cartera(libro).btc == 0


def test_con_vender_sin_posicion_o_mantener_no_hace_nada(bot: BotSimulado, libro: LibroDeOrdenes,
                                                        estrategia: EstrategiaManual) -> None:
    estrategia.decir(Senal.VENDER)
    bot.ejecutar_ciclo()
    estrategia.decir(Senal.MANTENER)
    bot.ejecutar_ciclo()
    assert libro.ordenes().tamanio() == 0
    assert cartera(libro).saldo_usdt == 10_000


def test_cada_decision_queda_en_el_historial_con_su_motivo(bot: BotSimulado, libro: LibroDeOrdenes) -> None:
    bot.ejecutar_ciclo()
    evento = libro.historial(1).primero()
    assert evento.tipo is TipoEvento.DECISION_BOT
    assert evento.descripcion == "El bot decidió MANTENER (confianza 0.25): la prueba pidió MANTENER"
    estado = bot.estado()
    assert estado.ultima_decision is not None and estado.ultima_decision.senal is Senal.MANTENER
    assert estado.ciclos == 1


# ---------- stop-loss y take-profit ----------


def test_stop_loss_vende_todo_aunque_la_estrategia_diga_comprar(
        bot: BotSimulado, libro: LibroDeOrdenes, fuente: FuenteFalsa, estrategia: EstrategiaManual) -> None:
    estrategia.decir(Senal.COMPRAR)
    bot.ejecutar_ciclo()  # compra a 100 (costo promedio 100,1 con comisión)
    fuente.precio = 95  # −5,09 % desde el costo
    bot.ejecutar_ciclo()
    venta = ultima_ejecutada(libro)
    assert venta.tipo is TipoOrden.VENTA
    assert venta.motivo.startswith("stop-loss")
    assert cartera(libro, 95).btc == 0
    assert hay_evento(libro, TipoEvento.STOP_LOSS)


def test_sin_llegar_al_stop_loss_no_vende(bot: BotSimulado, libro: LibroDeOrdenes, fuente: FuenteFalsa,
                                         estrategia: EstrategiaManual) -> None:
    estrategia.decir(Senal.COMPRAR)
    bot.ejecutar_ciclo()
    fuente.precio = 96  # −4,1 %
    estrategia.decir(Senal.MANTENER)
    bot.ejecutar_ciclo()
    assert cartera(libro, 96).btc > 0


def test_take_profit_vende_todo_al_ganar_diez_por_ciento(bot: BotSimulado, libro: LibroDeOrdenes,
                                                        fuente: FuenteFalsa, estrategia: EstrategiaManual) -> None:
    estrategia.decir(Senal.COMPRAR)
    bot.ejecutar_ciclo()
    fuente.precio = 111  # +10,9 % desde 100,1
    estrategia.decir(Senal.MANTENER)
    bot.ejecutar_ciclo()
    assert ultima_ejecutada(libro).motivo.startswith("take-profit")
    assert hay_evento(libro, TipoEvento.TAKE_PROFIT)
    assert cartera(libro, 111).ganancia_realizada > 0


# ---------- errores ----------


def test_un_error_de_la_fuente_queda_registrado_sin_romper_el_bot(bot: BotSimulado, libro: LibroDeOrdenes,
                                                                 fuente: FuenteFalsa) -> None:
    fuente.error = MercadoError("Binance no responde")
    bot.ejecutar_ciclo()
    assert bot.estado().ultimo_error == "Binance no responde"
    assert hay_evento(libro, TipoEvento.ERROR_BOT)
    fuente.error = None
    bot.ejecutar_ciclo()
    assert bot.estado().ultimo_error is None
    assert bot.estado().ciclos == 2


def test_el_bot_procesa_tambien_las_ordenes_manuales_pendientes(bot: BotSimulado, libro: LibroDeOrdenes) -> None:
    libro.crear_compra(100, "manual")
    bot.ejecutar_ciclo()
    assert libro.cantidad_pendientes() == 0
    assert libro.ordenes(EstadoOrden.EJECUTADA).tamanio() == 1


# ---------- iniciar y detener ----------


def test_iniciar_ejecuta_ciclos_periodicos_y_detener_los_para(bot: BotSimulado, libro: LibroDeOrdenes) -> None:
    rapido = ConfiguracionBot(1, "1h", 50, 0.2, 0.05, 0.1)
    estado = bot.iniciar(rapido)
    assert estado.activo and estado.estrategia == "manual"
    limite = time.monotonic() + 5
    while bot.estado().ciclos < 2 and time.monotonic() < limite:
        time.sleep(0.02)
    assert bot.estado().ciclos >= 2, "debía ejecutar al menos dos ciclos"
    with pytest.raises(OperacionInvalidaError):
        bot.iniciar(rapido)

    assert not bot.detener().activo
    ciclos = bot.estado().ciclos
    time.sleep(1.2)
    assert bot.estado().ciclos <= ciclos + 1, "no debía seguir ejecutando ciclos"
    assert hay_evento(libro, TipoEvento.BOT_INICIADO) and hay_evento(libro, TipoEvento.BOT_DETENIDO)
    assert not bot.detener().activo  # detener dos veces no falla


@pytest.mark.parametrize("datos", [
    {"segundos_entre_ciclos": 0}, {"intervalo": "2h"}, {"cantidad_velas": 1}, {"riesgo": 0},
    {"stop_loss": 1}, {"take_profit": 0},
])
def test_configuracion_invalida(datos: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ConfiguracionBot(**datos)  # type: ignore[arg-type]


def test_configuracion_por_defecto() -> None:
    assert ConfiguracionBot() == ConfiguracionBot(60, "1h", 200, 0.2, 0.05, 0.1)


class EstrategiaQueMira(EstrategiaManual):
    """Anota si el bot decía «en ciclo» mientras la estrategia trabajaba."""

    def __init__(self) -> None:
        super().__init__()
        self.bot: BotSimulado | None = None
        self.vio_en_ciclo: bool | None = None

    def evaluar(self, velas_hasta_ahora: ListaDoble[Vela] | None) -> Decision:
        assert self.bot is not None
        self.vio_en_ciclo = self.bot.estado().en_ciclo
        return super().evaluar(velas_hasta_ahora)


def test_encendido_desde_y_en_ciclo_muestran_que_trabaja(libro: LibroDeOrdenes, fuente: FuenteFalsa) -> None:
    estrategia = EstrategiaQueMira()
    reloj = iter(range(1_000, 10_000_000, 1_000))
    bot = BotSimulado(libro, fuente, estrategia, "BTCUSDT", reloj=lambda: next(reloj))
    estrategia.bot = bot
    assert bot.estado().encendido_desde is None and not bot.estado().en_ciclo
    bot.ejecutar_ciclo()
    assert estrategia.vio_en_ciclo is True, "durante el ciclo debía decir que está revisando"
    assert not bot.estado().en_ciclo, "al terminar ya no está en ciclo"
    try:
        desde = bot.iniciar(ConfiguracionBot(3600, "1h", 50, 0.2, 0.05, 0.1)).encendido_desde
        assert desde is not None and desde > 0
    finally:
        assert bot.detener().encendido_desde is None
