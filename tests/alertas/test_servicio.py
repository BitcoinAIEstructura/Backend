import time

import pytest

from bitcoinai.alertas.servicio import AlertaInvalidaError, AlertaNoEncontradaError, ServicioAlertas
from bitcoinai.alertas.tablero import Alerta, EstadoAlerta
from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.usuarios.servicio import Cliente
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import crear_entorno, datos


def entorno_con_usuarios() -> tuple[BaseDatos, int, int]:
    e = crear_entorno()
    ana, _ = e.servicio.registrar(datos(), Cliente("1.1.1.1", "x"))
    beto, _ = e.servicio.registrar(datos("beto@correo.co", "1098765432"), Cliente("1.1.1.1", "x"))
    return e.bd, ana.id, beto.id


def test_crear_valida_tipo_precio_y_lado() -> None:
    bd, ana, _ = entorno_con_usuarios()
    s = ServicioAlertas(bd, FuenteFalsa(), "BTCUSDT")
    with pytest.raises(AlertaInvalidaError, match="SUBE_A, BAJA_A"):
        s.crear(ana, "LATERAL", 90_000, 80_000)
    with pytest.raises(AlertaInvalidaError, match="mayor que 0"):
        s.crear(ana, "SUBE_A", -1, 80_000)
    with pytest.raises(AlertaInvalidaError, match="por encima del actual"):
        s.crear(ana, "SUBE_A", 79_000, 80_000)
    with pytest.raises(AlertaInvalidaError, match="por debajo del actual"):
        s.crear(ana, "baja_a", 81_000, 80_000)
    creada = s.crear(ana, "sube_a", 85_000, 80_000)
    assert (creada.estado, creada.precio) == (EstadoAlerta.ACTIVA, 85_000)


def test_maximo_por_usuario() -> None:
    bd, ana, beto = entorno_con_usuarios()
    s = ServicioAlertas(bd, FuenteFalsa(), "BTCUSDT")
    for i in range(20):
        s.crear(ana, "SUBE_A", 90_000 + i, 80_000)
    with pytest.raises(AlertaInvalidaError, match="Ya tienes 20"):
        s.crear(ana, "SUBE_A", 99_000, 80_000)
    s.crear(beto, "SUBE_A", 99_000, 80_000)  # los demás no se ven afectados


def test_disparar_guarda_y_avisa_solo_lo_que_se_cumple() -> None:
    bd, ana, beto = entorno_con_usuarios()
    avisos: list[Alerta] = []
    s = ServicioAlertas(bd, FuenteFalsa(), "BTCUSDT", al_disparar=avisos.append, reloj_ms=lambda: 123)
    a = s.crear(ana, "SUBE_A", 85_000, 80_000)
    s.crear(beto, "BAJA_A", 70_000, 80_000)
    assert tuple(x.id for x in s.revisar(86_000)) == (a.id,)
    assert [x.usuario_id for x in avisos] == [ana]
    guardada = s.listar(ana).obtener(0)
    assert (guardada.estado, guardada.disparada_en, guardada.precio_disparo) == (EstadoAlerta.DISPARADA, 123, 86_000)
    assert s.activas() == 1


def test_cancelar_solo_las_propias_y_activas() -> None:
    bd, ana, beto = entorno_con_usuarios()
    s = ServicioAlertas(bd, FuenteFalsa(), "BTCUSDT")
    a = s.crear(ana, "SUBE_A", 85_000, 80_000)
    with pytest.raises(AlertaNoEncontradaError):
        s.cancelar(beto, a.id)
    s.cancelar(ana, a.id)
    with pytest.raises(AlertaNoEncontradaError):
        s.cancelar(ana, a.id)
    assert s.revisar(100_000).esta_vacia()
    assert s.listar(ana).obtener(0).estado is EstadoAlerta.CANCELADA


def test_las_activas_sobreviven_a_un_reinicio() -> None:
    bd, ana, _ = entorno_con_usuarios()
    ServicioAlertas(bd, FuenteFalsa(), "BTCUSDT").crear(ana, "BAJA_A", 70_000, 80_000)
    otra_vez = ServicioAlertas(bd, FuenteFalsa(), "BTCUSDT")
    assert otra_vez.activas() == 1
    assert otra_vez.revisar(69_000).tamanio() == 1


def test_el_vigilante_revisa_solo_si_hay_alertas() -> None:
    bd, ana, _ = entorno_con_usuarios()
    fuente = FuenteFalsa(precio=80_000)
    avisos: list[Alerta] = []
    s = ServicioAlertas(bd, fuente, "BTCUSDT", al_disparar=avisos.append, periodo_s=0.02)
    s.iniciar()
    try:
        time.sleep(0.1)
        assert fuente.llamadas_precio == 0  # sin alertas, ni pregunta el precio
        s.crear(ana, "SUBE_A", 85_000, 80_000)
        fuente.precio = 90_000
        limite = time.monotonic() + 2
        while not avisos and time.monotonic() < limite:
            time.sleep(0.02)
        assert len(avisos) == 1
    finally:
        s.detener()


def test_migraciones_al_dia() -> None:
    assert migrar(BaseDatos(":memory:")) == 3
