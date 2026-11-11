import pytest

from bitcoinai.estructuras import Lista
from bitcoinai.simulacion import EstadoOrden, Orden, TipoOrden
from bitcoinai.simulacion.estadisticas import DIA_MS, calcular, dia_de, origen_de

AHORA = 1_762_900_000_000  # 2025-11-11, 22:26 UTC


def ejecutada(id_: int, tipo: TipoOrden, monto: float, precio: float, momento: int, motivo: str = "manual") -> Orden:
    cantidad = (monto * 0.999) / precio if tipo is TipoOrden.COMPRA else monto / precio
    return Orden(id_, tipo, monto, False, EstadoOrden.EJECUTADA, momento, momento, precio, cantidad,
                 monto * 0.001, motivo)


def test_origen_y_dia() -> None:
    assert origen_de(ejecutada(1, TipoOrden.COMPRA, 10, 1, 0, "piloto IA: sube")) == "ia"
    assert origen_de(ejecutada(1, TipoOrden.COMPRA, 10, 1, 0, "señal del bot: cruce")) == "bot"
    assert origen_de(ejecutada(1, TipoOrden.VENTA, 10, 1, 0, "take-profit: +10 %")) == "bot"
    assert origen_de(ejecutada(1, TipoOrden.COMPRA, 10, 1, 0)) == "manual"
    # 2025-11-11 03:00 UTC son las 22:00 del 10 de noviembre en Bogotá.
    assert dia_de(1_762_830_000_000) == dia_de(1_762_830_000_000 - 3_600_000)
    assert (dia_de(AHORA) - 5 * 3_600_000) % DIA_MS == 0  # medianoche de Bogotá = 05:00 UTC


def test_ganancias_aciertos_y_actividad() -> None:
    ordenes: Lista[Orden] = Lista()
    ordenes.agregar(ejecutada(1, TipoOrden.COMPRA, 1000, 100, AHORA - 3 * DIA_MS))
    ordenes.agregar(ejecutada(2, TipoOrden.VENTA, 1100 * 0.999, 110, AHORA - 2 * DIA_MS, "piloto IA: baja"))
    ordenes.agregar(ejecutada(3, TipoOrden.COMPRA, 1000, 100, AHORA - DIA_MS, "señal del bot: rsi"))
    ordenes.agregar(ejecutada(4, TipoOrden.VENTA, 900 * 0.999, 90, AHORA, "stop-loss: −10 %"))
    cancelada = Orden(5, TipoOrden.COMPRA, 50, False, EstadoOrden.CANCELADA, AHORA)
    ordenes.agregar(cancelada)
    e = calcular(ordenes, 10_000, 0.001, AHORA, dias=7)
    assert e.operaciones.tamanio() == 2
    gano, perdio = e.operaciones.primero(), e.operaciones.ultimo()
    assert gano.ganancia == pytest.approx(1100 * 0.999 * 0.999 - 1000, rel=1e-6)
    assert gano.origen == "ia" and perdio.origen == "bot" and perdio.ganancia < 0
    assert (e.ganadoras, e.perdedoras, e.tasa_acierto) == (1, 1, 0.5)
    assert e.mejor == gano.ganancia and e.peor == perdio.ganancia
    assert e.por_origen == {"manual": 1, "bot": 2, "ia": 1}
    assert e.actividad.tamanio() == 7
    assert sum(a.compras for a in e.actividad) == 2 and sum(a.ventas for a in e.actividad) == 2
    assert e.actividad.ultimo().ventas == 1


def test_sin_operaciones() -> None:
    e = calcular(Lista(), 10_000, 0.001, AHORA)
    assert e.tasa_acierto is None and e.mejor is None and e.actividad.tamanio() == 30
