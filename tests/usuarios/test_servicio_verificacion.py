"""Confirmar el correo con un código al crear la cuenta (con un buzón en memoria)."""

import re

import pytest

from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.notificaciones import BuzonMemoria
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.seguridad.contrasenas import PARAMETROS_RAPIDOS_PARA_PRUEBAS, HashContrasenas
from bitcoinai.usuarios.actividad import TipoActividad
from bitcoinai.usuarios.servicio import (
    CodigoInvalidoError,
    DemasiadosIntentosError,
    EsperaReenvioError,
    ServicioCuentas,
    VerificacionVencidaError,
    correo_enmascarado,
)
from tests.usuarios.entorno import CLIENTE, CONTRASENA, Reloj, datos


class Entorno:
    def __init__(self) -> None:
        bd = BaseDatos(":memory:")
        migrar(bd)
        self.reloj = Reloj()
        self.buzon = BuzonMemoria()
        self.servicio = ServicioCuentas(bd, Cifrador(bytes(32)), HashContrasenas(PARAMETROS_RAPIDOS_PARA_PRUEBAS),
                                        reloj_ms=self.reloj.ms, reloj_s=self.reloj, correo=self.buzon)

    def codigo(self) -> str:
        encontrado = re.search(r"\d{6}", self.buzon.ultimo().asunto)
        assert encontrado is not None
        return encontrado.group(0)


@pytest.fixture
def e() -> Entorno:
    return Entorno()


def test_registrar_manda_el_codigo_y_no_abre_sesion(e: Entorno) -> None:
    r = e.servicio.registrar(datos(), CLIENTE)
    assert r.token_sesion is None and r.token_verificacion is not None
    assert r.correo == "a***@correo.co"
    correo = e.buzon.ultimo()
    assert correo.destino == "ana@correo.co" and "Hola, Ana" in correo.texto
    codigo = e.codigo()
    assert codigo in correo.texto and codigo in correo.html
    assert "15 minutos" in correo.texto
    # Sin confirmar, la contraseña correcta no abre sesión: pide el código.
    inicio = e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE)
    assert inicio.token_sesion is None and inicio.token_verificacion is not None
    assert inicio.correo == "a***@correo.co"


def test_el_codigo_confirma_el_correo_y_abre_la_sesion(e: Entorno) -> None:
    r = e.servicio.registrar(datos(), CLIENTE)
    assert r.token_verificacion is not None
    usuario, token = e.servicio.verificar_correo(r.token_verificacion, e.codigo(), CLIENTE)
    assert usuario.correo == "ana@correo.co" and token
    tipos = [ev.tipo for ev in e.servicio.actividad.recientes(usuario.id)]
    assert TipoActividad.CORREO_VERIFICADO in tipos
    # Ya confirmado: entra directo, y el código no sirve dos veces.
    assert e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE).token_sesion is not None
    with pytest.raises(VerificacionVencidaError):
        e.servicio.verificar_correo(r.token_verificacion, e.codigo(), CLIENTE)


def test_codigo_equivocado_gasta_intentos_y_al_quinto_hay_que_pedir_otro(e: Entorno) -> None:
    token = e.servicio.registrar(datos(), CLIENTE).token_verificacion
    assert token is not None
    bueno = e.codigo()
    malo = "000000" if bueno != "000000" else "111111"
    for _ in range(4):
        with pytest.raises(CodigoInvalidoError):
            e.servicio.verificar_correo(token, malo, CLIENTE)
    with pytest.raises(VerificacionVencidaError):
        e.servicio.verificar_correo(token, malo, CLIENTE)
    with pytest.raises(VerificacionVencidaError):  # ni siquiera el bueno
        e.servicio.verificar_correo(token, bueno, CLIENTE)
    e.reloj.ahora += 61
    e.servicio.reenviar_codigo(token)
    assert e.servicio.verificar_correo(token, e.codigo(), CLIENTE)[1]


def test_el_codigo_vence_a_los_15_minutos(e: Entorno) -> None:
    token = e.servicio.registrar(datos(), CLIENTE).token_verificacion
    assert token is not None
    e.reloj.ahora += 15 * 60 + 1
    with pytest.raises(VerificacionVencidaError):
        e.servicio.verificar_correo(token, e.codigo(), CLIENTE)


def test_reenviar_espera_un_minuto_y_maximo_5_por_hora(e: Entorno) -> None:
    token = e.servicio.registrar(datos(), CLIENTE).token_verificacion
    assert token is not None
    with pytest.raises(EsperaReenvioError, match="Espera 60 s"):
        e.servicio.reenviar_codigo(token)
    viejo = e.codigo()
    for _ in range(4):
        e.reloj.ahora += 61
        assert e.servicio.reenviar_codigo(token) == "a***@correo.co"
    assert e.buzon.enviados.tamanio() == 5
    e.reloj.ahora += 61
    with pytest.raises(DemasiadosIntentosError):
        e.servicio.reenviar_codigo(token)
    # Solo sirve el último código enviado.
    if viejo != e.codigo():
        with pytest.raises(CodigoInvalidoError):
            e.servicio.verificar_correo(token, viejo, CLIENTE)


def test_iniciar_sesion_sin_confirmar_reenvia_solo_si_paso_un_minuto(e: Entorno) -> None:
    e.servicio.registrar(datos(), CLIENTE)
    e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE)
    assert e.buzon.enviados.tamanio() == 1  # el de hace un momento sigue sirviendo
    primero = e.codigo()
    e.reloj.ahora += 61
    inicio = e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE)
    assert e.buzon.enviados.tamanio() == 2
    assert inicio.token_verificacion is not None
    if primero != e.codigo():
        with pytest.raises(CodigoInvalidoError):
            e.servicio.verificar_correo(inicio.token_verificacion, primero, CLIENTE)
    assert e.servicio.verificar_correo(inicio.token_verificacion, e.codigo(), CLIENTE)[1]


def test_token_desconocido(e: Entorno) -> None:
    with pytest.raises(VerificacionVencidaError):
        e.servicio.verificar_correo("inventado", "123456", CLIENTE)
    with pytest.raises(VerificacionVencidaError):
        e.servicio.reenviar_codigo("")


def test_correo_enmascarado() -> None:
    assert correo_enmascarado("valentina@prueba.co") == "va*******@prueba.co"
    assert correo_enmascarado("ana@correo.co") == "a***@correo.co"
    assert correo_enmascarado("x@y.co") == "x***@y.co"
