import threading
from collections.abc import Iterator

import pytest

from bitcoinai.basedatos import BaseDatos
from bitcoinai.modelo import Intervalo
from bitcoinai.persistencia import AlmacenBaseDatos
from bitcoinai.simulacion.gestor import GestorSimulaciones
from tests.apoyo.fuente_falsa import FuenteFalsa, generar_velas
from tests.simulacion.test_publicacion import Grabador
from tests.usuarios.entorno import CLIENTE, crear_entorno, datos


@pytest.fixture
def bd() -> BaseDatos:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    e.servicio.registrar(datos("luis@correo.co", "79123456"), CLIENTE)
    return e.bd


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa(generar_velas(300, Intervalo.H1), 100.0)


@pytest.fixture
def gestor(bd: BaseDatos, fuente: FuenteFalsa) -> Iterator[GestorSimulaciones]:
    g = GestorSimulaciones(fuente, "BTCUSDT", crear_almacen=lambda u: AlmacenBaseDatos(bd, u))
    yield g


def test_cada_usuario_tiene_su_propia_cartera_y_sus_ordenes(gestor: GestorSimulaciones) -> None:
    gestor.libro(1).crear_compra(1000)
    gestor.libro(1).procesar_siguiente()
    assert gestor.libro(1).estado_cartera(100).saldo_usdt == 9_000
    assert gestor.libro(2).estado_cartera(100).saldo_usdt == 10_000
    assert gestor.libro(2).ordenes().esta_vacia()
    assert gestor.libro(2).crear_compra(5).id == 1  # la numeración también es propia
    assert gestor.libro(1) is gestor.libro(1)  # se carga una sola vez
    assert gestor.bot(1) is not gestor.bot(2)
    assert gestor.cantidad_cargadas() == 2


def test_se_recupera_al_reiniciar(bd: BaseDatos, fuente: FuenteFalsa, gestor: GestorSimulaciones) -> None:
    gestor.libro(1).crear_compra(1000)
    gestor.libro(1).procesar_siguiente()
    gestor.libro(1).crear_compra(50)
    otro = GestorSimulaciones(fuente, "BTCUSDT", crear_almacen=lambda u: AlmacenBaseDatos(bd, u))
    assert otro.libro(1).estado_cartera(100).saldo_usdt == 9_000
    assert otro.libro(1).cantidad_pendientes() == 1
    assert otro.libro(2).estado_cartera(100).saldo_usdt == 10_000


def test_eventos_con_su_dueno(fuente: FuenteFalsa) -> None:
    grabadores = {1: Grabador(), 2: Grabador()}
    gestor = GestorSimulaciones(fuente, "BTCUSDT", crear_publicador=grabadores.__getitem__)
    gestor.libro(2).crear_compra(10)
    assert grabadores[1].eventos == ()
    assert grabadores[2].estados() == ("orden:PENDIENTE",)


def test_carga_concurrente_crea_una_sola_simulacion(gestor: GestorSimulaciones) -> None:
    libros = []
    hilos = [threading.Thread(target=lambda: libros.append(gestor.libro(1))) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert len({id(libro) for libro in libros}) == 1


def test_limite_de_bots_a_la_vez(fuente: FuenteFalsa) -> None:
    from bitcoinai.simulacion import ConfiguracionBot, OperacionInvalidaError

    gestor = GestorSimulaciones(fuente, "BTCUSDT", maximo_bots=1)
    lento = ConfiguracionBot(segundos_entre_ciclos=3600)
    try:
        assert gestor.iniciar_bot(1, lento).activo
        with pytest.raises(OperacionInvalidaError, match="ya está en marcha"):
            gestor.iniciar_bot(1, lento)
        with pytest.raises(OperacionInvalidaError, match="máximo 1"):
            gestor.iniciar_bot(2, lento)
        assert gestor.bots_activos() == 1
        gestor.bot(1).detener()
        assert gestor.iniciar_bot(2, lento).activo
    finally:
        gestor.detener_todos()
    assert gestor.bots_activos() == 0
