"""Pruebas del almacén en archivos y de la recarga del libro de órdenes."""

import json
from pathlib import Path

import pytest

from bitcoinai.estructuras import Lista
from bitcoinai.mercado import MercadoError
from bitcoinai.persistencia import CARTERA, HISTORIAL, ORDENES, AlmacenArchivos
from bitcoinai.simulacion import (
    Cartera,
    DatosCartera,
    EstadoOrden,
    EstadoSimulacion,
    Evento,
    LibroDeOrdenes,
    Orden,
    TipoEvento,
    TipoOrden,
)
from tests.apoyo.fuente_falsa import FuenteFalsa


def lista_de[T](*valores: T) -> Lista[T]:
    resultado: Lista[T] = Lista()
    for valor in valores:
        resultado.agregar(valor)
    return resultado


def estado_de_ejemplo() -> EstadoSimulacion:
    pendiente = Orden(3, TipoOrden.VENTA, None, True, EstadoOrden.PENDIENTE, 30, motivo="salir")
    ejecutada = Orden(1, TipoOrden.COMPRA, 500.0, False, EstadoOrden.EJECUTADA, 10, 11, 100.0, 4.995, 0.5,
                      "manual", "Compró 4.99500000 BTC")
    cancelada = Orden(2, TipoOrden.COMPRA, 200.0, False, EstadoOrden.CANCELADA, 20, detalle="Cancelada.")
    eventos = lista_de(Evento(10, TipoEvento.ORDEN_CREADA, 1, "creada"),
                       Evento(11, TipoEvento.DECISION_BOT, None, "ñ"))
    return EstadoSimulacion(DatosCartera(10_000, 9_500, 4.995, 500, 0, 0.5), 4, lista_de(pendiente),
                            lista_de(ejecutada, cancelada), lista_de(1, 2, 3), eventos)


def test_guarda_y_carga_el_mismo_estado(tmp_path: Path) -> None:
    almacen = AlmacenArchivos(tmp_path / "datos")
    original = estado_de_ejemplo()
    almacen.guardar(original)
    cargado = almacen.cargar()
    assert cargado is not None
    assert cargado.cartera == original.cartera
    assert cargado.siguiente_id == 4
    assert tuple(cargado.pendientes) == tuple(original.pendientes)
    assert tuple(cargado.registro) == tuple(original.registro)
    assert tuple(cargado.creadas) == (1, 2, 3)
    assert tuple(cargado.eventos) == tuple(original.eventos)
    assert not any(p.name.endswith(".tmp") for p in (tmp_path / "datos").iterdir())


def test_formato_de_los_archivos(tmp_path: Path) -> None:
    AlmacenArchivos(tmp_path).guardar(estado_de_ejemplo())
    cartera = json.loads((tmp_path / CARTERA).read_text(encoding="utf-8"))
    assert cartera == {"version": 1, "cartera": {"saldoInicial": 10_000, "saldoUsdt": 9_500, "btc": 4.995,
                                                 "costoPosicion": 500, "gananciaRealizada": 0,
                                                 "comisionesPagadas": 0.5}}
    ordenes = json.loads((tmp_path / ORDENES).read_text(encoding="utf-8"))
    assert list(ordenes) == ["version", "siguienteId", "pendientes", "registro", "creadas"]
    assert list(ordenes["pendientes"][0]) == ["id", "tipo", "monto", "todo", "estado", "creadaEn", "ejecutadaEn",
                                              "precioEjecucion", "cantidadBtc", "comision", "motivo", "detalle"]
    historial = json.loads((tmp_path / HISTORIAL).read_text(encoding="utf-8"))
    assert historial["eventos"][1] == {"momento": 11, "tipo": "DECISION_BOT", "idOrden": None, "descripcion": "ñ"}


def test_sin_archivos_no_hay_estado(tmp_path: Path) -> None:
    assert AlmacenArchivos(tmp_path / "no-existe").cargar() is None


@pytest.mark.parametrize("contenido", [
    "esto no es json",
    '{"version":2,"cartera":{}}',
    '{"version":1,"cartera":{"saldoInicial":-1,"saldoUsdt":0,"btc":0,"costoPosicion":0,'
    '"gananciaRealizada":0,"comisionesPagadas":0}}',
    '{"version":1,"cartera":{"saldoInicial":"mucho"}}',
])
def test_cartera_danada_se_aparta_y_se_empieza_limpio(tmp_path: Path, contenido: str) -> None:
    almacen = AlmacenArchivos(tmp_path)
    almacen.guardar(estado_de_ejemplo())
    (tmp_path / CARTERA).write_text(contenido, encoding="utf-8")
    cargado = almacen.cargar()
    assert cargado is not None  # queda el historial, que se carga aparte
    assert cargado.cartera is None
    assert tuple(cargado.pendientes) == ()
    assert len(tuple(cargado.eventos)) == 2
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert any(n.startswith("cartera.json.danado-") for n in nombres)
    assert any(n.startswith("ordenes.json.danado-") for n in nombres)  # van juntas
    assert CARTERA not in nombres and ORDENES not in nombres


def test_orden_en_la_cola_sin_estar_pendiente_es_un_dano(tmp_path: Path) -> None:
    almacen = AlmacenArchivos(tmp_path)
    almacen.guardar(estado_de_ejemplo())
    datos = json.loads((tmp_path / ORDENES).read_text(encoding="utf-8"))
    datos["pendientes"][0]["estado"] = "EJECUTADA"
    (tmp_path / ORDENES).write_text(json.dumps(datos), encoding="utf-8")
    cargado = almacen.cargar()
    assert cargado is not None and cargado.cartera is None


def test_falta_uno_de_los_dos_archivos(tmp_path: Path) -> None:
    almacen = AlmacenArchivos(tmp_path)
    almacen.guardar(estado_de_ejemplo())
    (tmp_path / ORDENES).unlink()
    (tmp_path / HISTORIAL).unlink()
    assert almacen.cargar() is None
    assert any(p.name.startswith("cartera.json.danado-") for p in tmp_path.iterdir())


def test_historial_danado_no_afecta_a_la_cartera(tmp_path: Path) -> None:
    almacen = AlmacenArchivos(tmp_path)
    almacen.guardar(estado_de_ejemplo())
    (tmp_path / HISTORIAL).write_text('{"version":1,"eventos":[{"momento":1}]}', encoding="utf-8")
    cargado = almacen.cargar()
    assert cargado is not None
    assert cargado.cartera is not None
    assert tuple(cargado.eventos) == ()


# ---------- el libro de órdenes con almacén ----------


def nuevo_libro(directorio: Path, fuente: FuenteFalsa) -> tuple[LibroDeOrdenes, bool]:
    libro = LibroDeOrdenes(Cartera(), fuente, "BTCUSDT")
    return libro, libro.usar_almacen(AlmacenArchivos(directorio))


def test_el_libro_recupera_todo_en_el_mismo_orden(tmp_path: Path) -> None:
    fuente = FuenteFalsa()
    libro, recuperado = nuevo_libro(tmp_path, fuente)
    assert not recuperado
    libro.crear_compra(500)
    libro.procesar_siguiente()
    for monto in (100, 200, 300):
        libro.crear_compra(monto)
    libro.cancelar(3)

    otro, recuperado = nuevo_libro(tmp_path, fuente)
    assert recuperado
    assert tuple(otro.ordenes()) == tuple(libro.ordenes())
    assert tuple(otro.historial(100)) == tuple(libro.historial(100))  # el más reciente arriba
    assert otro.estado_cartera(100) == libro.estado_cartera(100)
    assert otro.crear_compra(50).id == 5  # sigue la numeración
    procesada = otro.procesar_siguiente()
    assert procesada is not None and procesada.id == 2  # la cola sigue en orden FIFO
    deshecha = otro.deshacer_ultima_orden()  # la pila de creadas también: sale la última (#5)
    assert deshecha is not None and deshecha.id == 5


def test_una_orden_a_medio_procesar_vuelve_al_frente(tmp_path: Path) -> None:
    fuente = FuenteFalsa()
    libro, _ = nuevo_libro(tmp_path, fuente)
    libro.crear_compra(100)
    libro.crear_compra(200)
    fuente.error = MercadoError("caída")
    with pytest.raises(MercadoError):
        libro.procesar_siguiente()
    fuente.error = None
    otro, _ = nuevo_libro(tmp_path, fuente)
    assert tuple(o.id for o in otro.ordenes(EstadoOrden.PENDIENTE)) == (1, 2)


def test_la_instantanea_guarda_la_orden_en_proceso_como_pendiente(tmp_path: Path) -> None:
    libro, _ = nuevo_libro(tmp_path, FuenteFalsa())
    libro.crear_compra(100)
    libro.crear_compra(200)
    libro._en_proceso = libro._pendientes.desencolar().con_estado(EstadoOrden.PROCESANDO, None)
    foto = libro._instantanea()
    assert tuple((o.id, o.estado) for o in foto.pendientes) == ((1, EstadoOrden.PENDIENTE),
                                                                 (2, EstadoOrden.PENDIENTE))


def test_un_fallo_al_guardar_no_deshace_la_operacion(caplog: pytest.LogCaptureFixture) -> None:
    class AlmacenRoto:
        def guardar(self, estado: EstadoSimulacion) -> None:
            raise OSError("disco lleno")

        def cargar(self) -> EstadoSimulacion | None:
            return None

    libro = LibroDeOrdenes(Cartera(), FuenteFalsa(), "BTCUSDT")
    libro.usar_almacen(AlmacenRoto())
    assert libro.crear_compra(100).id == 1
    assert libro.cantidad_pendientes() == 1
    assert "disco lleno" in caplog.text
