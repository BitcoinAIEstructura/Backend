import itertools
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from bitcoinai.estructuras import Lista, ListaDoble
from bitcoinai.mercado import MercadoError
from bitcoinai.modelo import Intervalo, Vela
from bitcoinai.simulacion import (
    Cartera,
    EstadoOrden,
    LibroDeOrdenes,
    OperacionInvalidaError,
    Orden,
    OrdenNoEncontradaError,
    TipoEvento,
    TipoOrden,
)
from tests.apoyo.fuente_falsa import FuenteFalsa


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa(ListaDoble(), 100.0)


@pytest.fixture
def libro(fuente: FuenteFalsa) -> LibroDeOrdenes:
    contador = itertools.count(1_000)
    return LibroDeOrdenes(Cartera(), fuente, "BTCUSDT", 0.001, lambda: next(contador))


def ids(ordenes: Lista[Orden]) -> str:
    return " ".join(str(o.id) for o in ordenes)


# ---------- FIFO ----------


def test_las_ordenes_se_ejecutan_en_orden_de_llegada(libro: LibroDeOrdenes) -> None:
    for monto in (100, 200, 300):
        libro.crear_compra(monto)
    assert ids(libro.ordenes(EstadoOrden.PENDIENTE)) == "1 2 3"
    procesadas = tuple(libro.procesar_siguiente() for _ in range(3))
    assert tuple(o.id for o in procesadas if o is not None) == (1, 2, 3)
    assert libro.procesar_siguiente() is None
    ejecutadas = libro.ordenes(EstadoOrden.EJECUTADA)
    assert ids(ejecutadas) == "1 2 3"
    primera, segunda = ejecutadas.obtener(0).ejecutada_en, ejecutadas.obtener(1).ejecutada_en
    assert primera is not None and segunda is not None and primera < segunda


def test_orden_nueva_queda_pendiente_con_sus_datos(libro: LibroDeOrdenes) -> None:
    orden = libro.crear_compra(500, "  ")
    assert (orden.id, orden.tipo, orden.monto, orden.estado, orden.motivo) == (
        1, TipoOrden.COMPRA, 500, EstadoOrden.PENDIENTE, "manual")
    assert orden.ejecutada_en is None and orden.precio_ejecucion is None
    assert libro.cantidad_pendientes() == 1


# ---------- ejecución con comisión ----------


def test_compra_y_venta_con_comision_actualizan_la_cartera(libro: LibroDeOrdenes, fuente: FuenteFalsa) -> None:
    libro.crear_compra(500)
    compra = libro.procesar_siguiente()
    assert compra is not None and compra.estado is EstadoOrden.EJECUTADA
    assert (compra.precio_ejecucion, compra.comision) == (100, pytest.approx(0.5))
    assert compra.cantidad_btc == pytest.approx(4.995)
    tras = libro.estado_cartera(100)
    assert (tras.saldo_usdt, tras.btc) == (pytest.approx(9_500), pytest.approx(4.995))

    fuente.precio = 120
    libro.crear_venta(120)  # 1 BTC
    venta = libro.procesar_siguiente()
    assert venta is not None
    assert (venta.cantidad_btc, venta.comision) == (pytest.approx(1.0), pytest.approx(0.12))
    fin = libro.estado_cartera(120)
    assert fin.btc == pytest.approx(3.995)
    assert fin.saldo_usdt == pytest.approx(9_500 + 120 - 0.12)
    assert fin.comisiones_pagadas == pytest.approx(0.62)


def test_venta_de_todo_guarda_el_monto_obtenido(libro: LibroDeOrdenes, fuente: FuenteFalsa) -> None:
    libro.crear_compra(1000)
    libro.procesar_siguiente()
    fuente.precio = 110
    libro.crear_venta_total("salida")
    venta = libro.procesar_siguiente()
    assert venta is not None and venta.todo
    assert venta.monto == pytest.approx(9.99 * 110)
    assert libro.estado_cartera(110).btc == 0


# ---------- rechazos ----------


def test_compra_sin_saldo_suficiente_se_rechaza_con_motivo(libro: LibroDeOrdenes) -> None:
    libro.crear_compra(20_000)
    orden = libro.procesar_siguiente()
    assert orden is not None and orden.estado is EstadoOrden.RECHAZADA
    assert orden.detalle == "Saldo insuficiente: la compra necesita 20000.00 USDT y hay 10000.00"
    assert orden.precio_ejecucion == 100
    assert libro.estado_cartera(100).saldo_usdt == 10_000
    assert libro.historial(1).primero().tipo is TipoEvento.ORDEN_RECHAZADA


def test_venta_sin_btc_se_rechaza(libro: LibroDeOrdenes) -> None:
    libro.crear_venta(50)
    libro.crear_venta_total()
    primera, segunda = libro.procesar_siguiente(), libro.procesar_siguiente()
    assert primera is not None and primera.estado is EstadoOrden.RECHAZADA
    assert segunda is not None and segunda.detalle == "No hay BTC para vender"


# ---------- cancelar y deshacer ----------


def test_cancelar_una_orden_del_medio_conserva_el_orden_de_las_demas(libro: LibroDeOrdenes) -> None:
    for monto in (100, 200, 300, 400):
        libro.crear_compra(monto)
    assert libro.cancelar(2).estado is EstadoOrden.CANCELADA
    assert ids(libro.ordenes(EstadoOrden.PENDIENTE)) == "1 3 4"
    procesadas = tuple(libro.procesar_siguiente() for _ in range(3))
    assert tuple(o.id for o in procesadas if o is not None) == (1, 3, 4)
    assert ids(libro.ordenes(EstadoOrden.CANCELADA)) == "2"


def test_cancelar_algo_que_no_esta_pendiente_falla(libro: LibroDeOrdenes) -> None:
    libro.crear_compra(100)
    libro.procesar_siguiente()
    with pytest.raises(OperacionInvalidaError, match="La orden #1 ya no está pendiente: está EJECUTADA"):
        libro.cancelar(1)
    with pytest.raises(OrdenNoEncontradaError):
        libro.cancelar(99)


def test_deshacer_quita_la_ultima_creada_y_luego_la_anterior(libro: LibroDeOrdenes) -> None:
    for monto in (100, 200, 300):
        libro.crear_compra(monto)
    deshecha = libro.deshacer_ultima_orden()
    assert deshecha is not None and (deshecha.id, deshecha.estado) == (3, EstadoOrden.CANCELADA)
    assert ids(libro.ordenes(EstadoOrden.PENDIENTE)) == "1 2"
    segunda = libro.deshacer_ultima_orden()
    assert segunda is not None and segunda.id == 2
    assert ids(libro.ordenes(EstadoOrden.PENDIENTE)) == "1"
    assert libro.historial(1).primero().tipo is TipoEvento.ORDEN_DESHECHA


def test_deshacer_no_hace_nada_si_la_ultima_ya_se_ejecuto(libro: LibroDeOrdenes) -> None:
    assert libro.deshacer_ultima_orden() is None
    libro.crear_compra(100)
    libro.procesar_siguiente()
    assert libro.deshacer_ultima_orden() is None
    assert ids(libro.ordenes(EstadoOrden.EJECUTADA)) == "1"


# ---------- historial ----------


def test_historial_devuelve_lo_mas_reciente_primero_sin_borrarlo(libro: LibroDeOrdenes) -> None:
    libro.crear_compra(100)
    libro.procesar_siguiente()
    libro.crear_compra(200)
    libro.cancelar(2)
    eventos = libro.historial(10)
    assert tuple(e.tipo for e in eventos) == (TipoEvento.ORDEN_CANCELADA, TipoEvento.ORDEN_CREADA,
                                             TipoEvento.ORDEN_EJECUTADA, TipoEvento.ORDEN_CREADA)
    assert eventos.primero().id_orden == 2
    # Leerlo no lo modifica: la segunda lectura da lo mismo.
    assert libro.historial(10).tamanio() == 4
    assert libro.historial(2).tamanio() == 2
    assert libro.historial(2).primero().tipo is TipoEvento.ORDEN_CANCELADA


# ---------- fallos y estado PROCESANDO ----------


def test_si_falla_el_precio_la_orden_vuelve_al_frente_de_la_cola(libro: LibroDeOrdenes, fuente: FuenteFalsa) -> None:
    libro.crear_compra(100)
    libro.crear_compra(200)
    fuente.error = MercadoError("Binance caído")
    with pytest.raises(MercadoError):
        libro.procesar_siguiente()
    assert ids(libro.ordenes(EstadoOrden.PENDIENTE)) == "1 2"
    fuente.error = None
    procesada = libro.procesar_siguiente()
    assert procesada is not None and procesada.id == 1


class FuenteLenta:
    """Fuente cuyo precio tarda hasta que la prueba la libera."""

    def __init__(self) -> None:
        self.entro = threading.Event()
        self.liberar = threading.Event()

    def obtener_velas(self, simbolo: str, intervalo: Intervalo, cantidad: int) -> ListaDoble[Vela]:
        return ListaDoble()

    def obtener_precio_actual(self, simbolo: str) -> float:
        self.entro.set()
        self.liberar.wait(5)
        return 100.0


def test_mientras_se_consulta_el_precio_la_orden_esta_procesando_y_no_se_puede_cancelar() -> None:
    lenta = FuenteLenta()
    libro = LibroDeOrdenes(Cartera(), lenta, "BTCUSDT")
    libro.crear_compra(100)
    with ThreadPoolExecutor(max_workers=1) as hilo:
        proceso = hilo.submit(libro.procesar_siguiente)
        try:
            assert lenta.entro.wait(5)
            # Mientras tanto se puede consultar y crear sin bloquearse.
            assert ids(libro.ordenes(EstadoOrden.PROCESANDO)) == "1"
            libro.crear_compra(50)
            with pytest.raises(OperacionInvalidaError, match="se está procesando"):
                libro.cancelar(1)
        finally:
            lenta.liberar.set()
        proceso.result(timeout=5)
    assert ids(libro.ordenes(EstadoOrden.EJECUTADA)) == "1"
    assert ids(libro.ordenes(EstadoOrden.PENDIENTE)) == "2"


# ---------- concurrencia ----------


def test_varios_hilos_creando_a_la_vez_no_pierden_ninguna_orden(libro: LibroDeOrdenes) -> None:
    hilos, por_hilo = 8, 250
    largada = threading.Barrier(hilos)

    def crear() -> None:
        largada.wait()
        for _ in range(por_hilo):
            libro.crear_compra(1, "hilo")

    with ThreadPoolExecutor(max_workers=hilos) as ejecutor:
        for futuro in [ejecutor.submit(crear) for _ in range(hilos)]:
            futuro.result(timeout=10)
    assert libro.cantidad_pendientes() == hilos * por_hilo
    assert len({o.id for o in libro.ordenes(EstadoOrden.PENDIENTE)}) == hilos * por_hilo
    assert libro.historial(10_000).tamanio() == hilos * por_hilo


def test_crear_y_procesar_a_la_vez_desde_varios_hilos_cuadra_las_cuentas(libro: LibroDeOrdenes) -> None:
    def crear() -> None:
        for _ in range(100):
            libro.crear_compra(10)

    def procesar() -> None:
        for _ in range(150):
            libro.procesar_siguiente()

    with ThreadPoolExecutor(max_workers=6) as ejecutor:
        trabajos = [ejecutor.submit(f) for _ in range(3) for f in (crear, procesar)]
        for trabajo in trabajos:
            trabajo.result(timeout=10)
    while libro.procesar_siguiente() is not None:
        pass  # vacía lo que haya quedado
    assert libro.ordenes(EstadoOrden.EJECUTADA).tamanio() == 300
    assert libro.estado_cartera(100).saldo_usdt == pytest.approx(10_000 - 3000)


# ---------- validación ----------


def test_datos_invalidos_al_crear(libro: LibroDeOrdenes) -> None:
    for crear in (lambda: libro.crear_compra(0), lambda: libro.crear_compra(-5),
                  lambda: libro.crear_orden(TipoOrden.COMPRA, None, True, None),
                  lambda: libro.crear_orden(TipoOrden.VENTA, 10.0, True, None),
                  lambda: libro.crear_orden(TipoOrden.VENTA, float("nan"), False, None)):
        with pytest.raises(ValueError):
            crear()
    with pytest.raises(OrdenNoEncontradaError):
        libro.obtener(5)
    assert libro.cantidad_pendientes() == 0


def test_pila_deshacer_y_tamanios_sin_cambiar_nada(libro: LibroDeOrdenes) -> None:
    for monto in (10, 20, 30):
        libro.crear_compra(monto)
    libro.procesar_siguiente()
    assert tuple(libro.pila_deshacer(2)) == (3, 2)
    assert tuple(libro.pila_deshacer(10)) == (3, 2, 1)
    assert libro.tamanios() == (2, 1, 4, 3)  # 2 en cola, 1 en registro, 4 eventos, 3 ids creados
    assert libro.deshacer_ultima_orden() is not None  # la pila quedó intacta
