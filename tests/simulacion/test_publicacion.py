"""El libro de órdenes y el bot avisan sus cambios a un PublicadorEventos."""

import time

import pytest

from bitcoinai.estrategia import Decision, Senal
from bitcoinai.mercado import MercadoError
from bitcoinai.modelo import Intervalo
from bitcoinai.simulacion import (
    BotSimulado,
    Cartera,
    ConfiguracionBot,
    EstadoCartera,
    EstadoOrden,
    LibroDeOrdenes,
    Orden,
)
from tests.apoyo.fuente_falsa import FuenteFalsa, generar_velas
from tests.simulacion.estrategia_manual import EstrategiaManual


class Grabador:
    def __init__(self) -> None:
        self.eventos: tuple[tuple[str, object], ...] = ()

    def publicar(self, tipo: str, datos: object) -> None:
        self.eventos += ((tipo, datos),)

    def estados(self) -> tuple[str, ...]:
        return tuple(f"{t}:{d.estado.name}" if isinstance(d, Orden) else t for t, d in self.eventos)

    def senales(self) -> tuple[Senal, ...]:
        return tuple(d.senal for t, d in self.eventos if t == "senal" and isinstance(d, Decision))


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa(generar_velas(300, Intervalo.H1), 100.0)


def test_el_libro_publica_cada_cambio_de_estado(fuente: FuenteFalsa) -> None:
    grabador = Grabador()
    libro = LibroDeOrdenes(Cartera(), fuente, "BTCUSDT")
    libro.usar_publicador(grabador)
    libro.crear_compra(100)
    libro.procesar_siguiente()
    assert grabador.estados() == ("orden:PENDIENTE", "orden:PROCESANDO", "orden:EJECUTADA", "cartera")
    cartera = grabador.eventos[-1][1]
    assert isinstance(cartera, EstadoCartera) and cartera.saldo_usdt == 9_900

    grabador.eventos = ()
    libro.crear_venta(1_000_000)
    libro.procesar_siguiente()
    assert grabador.estados() == ("orden:PENDIENTE", "orden:PROCESANDO", "orden:RECHAZADA")  # sin "cartera"

    grabador.eventos = ()
    libro.crear_compra(10)
    libro.crear_compra(20)
    libro.cancelar(3)
    libro.deshacer_ultima_orden()
    assert grabador.estados() == ("orden:PENDIENTE", "orden:PENDIENTE", "orden:CANCELADA", "orden:CANCELADA")


def test_si_falla_el_precio_publica_que_la_orden_vuelve_a_pendiente(fuente: FuenteFalsa) -> None:
    grabador = Grabador()
    libro = LibroDeOrdenes(Cartera(), fuente, "BTCUSDT")
    libro.usar_publicador(grabador)
    libro.crear_compra(100)
    fuente.error = MercadoError("caída")
    with pytest.raises(MercadoError):
        libro.procesar_siguiente()
    assert grabador.estados() == ("orden:PENDIENTE", "orden:PROCESANDO", "orden:PENDIENTE")
    assert libro.obtener(1).estado is EstadoOrden.PENDIENTE


def test_el_bot_publica_la_senal_solo_cuando_cambia(fuente: FuenteFalsa) -> None:
    grabador = Grabador()
    estrategia = EstrategiaManual()
    bot = BotSimulado(LibroDeOrdenes(Cartera(), fuente, "BTCUSDT"), fuente, estrategia, "BTCUSDT")
    bot.usar_publicador(grabador)

    bot.ejecutar_ciclo()
    bot.ejecutar_ciclo()
    assert grabador.senales() == (Senal.MANTENER,)  # la primera siempre; la repetida no
    estrategia.decir(Senal.COMPRAR)
    bot.ejecutar_ciclo()
    bot.ejecutar_ciclo()
    assert grabador.senales() == (Senal.MANTENER, Senal.COMPRAR)

    # Al iniciar se vuelve a publicar la primera decisión aunque no haya cambiado.
    bot.iniciar(ConfiguracionBot(segundos_entre_ciclos=3600))
    try:
        limite = time.monotonic() + 5
        while len(grabador.senales()) < 3 and time.monotonic() < limite:
            time.sleep(0.01)
    finally:
        bot.detener()
    assert grabador.senales() == (Senal.MANTENER, Senal.COMPRAR, Senal.COMPRAR)
