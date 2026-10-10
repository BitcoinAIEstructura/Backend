import pytest

from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.mercado import MercadoError
from bitcoinai.persistencia.almacen_bd import AlmacenBaseDatos
from bitcoinai.simulacion import Cartera, EstadoOrden, LibroDeOrdenes
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.persistencia.test_almacen import estado_de_ejemplo
from tests.usuarios.entorno import CLIENTE, crear_entorno, datos


@pytest.fixture
def bd() -> BaseDatos:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    e.servicio.registrar(datos("luis@correo.co", "79123456"), CLIENTE)
    return e.bd


def test_sin_nada_guardado(bd: BaseDatos) -> None:
    assert AlmacenBaseDatos(bd, 1).cargar() is None


def test_guarda_y_carga_el_mismo_estado(bd: BaseDatos) -> None:
    almacen = AlmacenBaseDatos(bd, 1)
    original = estado_de_ejemplo()
    almacen.guardar(original)
    almacen.guardar(original)  # guardar dos veces reemplaza, no duplica
    cargado = almacen.cargar()
    assert cargado is not None
    assert cargado.cartera == original.cartera and cargado.siguiente_id == 4
    assert tuple(cargado.pendientes) == tuple(original.pendientes)
    assert tuple(cargado.registro) == tuple(original.registro)
    assert tuple(cargado.creadas) == (1, 2, 3)
    assert tuple(cargado.eventos) == tuple(original.eventos)


def test_cada_usuario_tiene_lo_suyo(bd: BaseDatos) -> None:
    AlmacenBaseDatos(bd, 1).guardar(estado_de_ejemplo())
    assert AlmacenBaseDatos(bd, 2).cargar() is None


def test_datos_invalidos_empiezan_limpio(bd: BaseDatos, caplog: pytest.LogCaptureFixture) -> None:
    almacen = AlmacenBaseDatos(bd, 1)
    almacen.guardar(estado_de_ejemplo())
    bd.ejecutar("UPDATE ordenes SET estado = 'RARO' WHERE usuario_id = 1")
    assert almacen.cargar() is None
    assert "inutilizable" in caplog.text


def test_el_libro_recupera_todo_en_el_mismo_orden(bd: BaseDatos) -> None:
    fuente = FuenteFalsa()
    libro = LibroDeOrdenes(Cartera(), fuente, "BTCUSDT")
    assert not libro.usar_almacen(AlmacenBaseDatos(bd, 1))
    libro.crear_compra(500)
    libro.procesar_siguiente()
    for monto in (100, 200, 300):
        libro.crear_compra(monto)
    libro.cancelar(3)
    fuente.error = MercadoError("caída")
    with pytest.raises(MercadoError):  # la #2 queda al frente otra vez
        libro.procesar_siguiente()
    fuente.error = None

    otro = LibroDeOrdenes(Cartera(), fuente, "BTCUSDT")
    assert otro.usar_almacen(AlmacenBaseDatos(bd, 1))
    assert tuple(otro.ordenes()) == tuple(libro.ordenes())
    assert tuple(otro.historial(100)) == tuple(libro.historial(100))
    assert otro.estado_cartera(100) == libro.estado_cartera(100)
    assert tuple(o.id for o in otro.ordenes(EstadoOrden.PENDIENTE)) == (2, 4)
    assert otro.crear_compra(5).id == 5
    deshecha = otro.deshacer_ultima_orden()
    assert deshecha is not None and deshecha.id == 5


def test_base_sin_migrar_no_sirve() -> None:
    import sqlite3

    with pytest.raises(sqlite3.OperationalError):
        AlmacenBaseDatos(BaseDatos(":memory:"), 1).cargar()
    base = BaseDatos(":memory:")
    migrar(base)
    assert AlmacenBaseDatos(base, 1).cargar() is None
