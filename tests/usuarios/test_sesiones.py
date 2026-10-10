import pytest

from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.usuarios.modelo import DatosRegistro
from bitcoinai.usuarios.repositorio import RepositorioUsuarios
from bitcoinai.usuarios.sesiones import (
    DURACION_DESAFIO,
    DURACION_SESION,
    INACTIVIDAD_MAXIMA,
    INTENTOS_DESAFIO,
    MINUTO,
    RepositorioSesiones,
)


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1_000_000

    def __call__(self) -> int:
        return self.ahora


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def sesiones(reloj: Reloj) -> RepositorioSesiones:
    bd = BaseDatos(":memory:")
    migrar(bd)
    usuarios = RepositorioUsuarios(bd, Cifrador(bytes(32)))
    for correo, documento in (("ana@correo.co", "1023456789"), ("luis@correo.co", "79123456")):
        usuarios.crear(DatosRegistro.validar("Ana", "Pérez", correo, "CC", documento, "3001234567",
                                             "Luna-Roja-2026"), "h")
    return RepositorioSesiones(bd, reloj)


def test_crear_y_validar(sesiones: RepositorioSesiones, reloj: Reloj) -> None:
    token, sesion = sesiones.crear(1, "127.0.0.1", "Firefox " * 100)
    assert len(sesion.agente) == 200
    reloj.ahora += 10 * MINUTO
    validada = sesiones.validar(token)
    assert validada is not None and validada.usuario_id == 1 and validada.ultima_actividad == reloj.ahora
    assert sesiones.validar("token-inventado") is None


def test_expira_por_inactividad_y_por_duracion(sesiones: RepositorioSesiones, reloj: Reloj) -> None:
    token, _ = sesiones.crear(1, "ip", "ag")
    reloj.ahora += INACTIVIDAD_MAXIMA + 1
    assert sesiones.validar(token) is None
    token, _ = sesiones.crear(1, "ip", "ag")
    for _ in range(DURACION_SESION // INACTIVIDAD_MAXIMA):
        reloj.ahora += INACTIVIDAD_MAXIMA - MINUTO  # usada a tiempo cada vez…
        if sesiones.validar(token) is None:
            break
    reloj.ahora += INACTIVIDAD_MAXIMA - MINUTO
    assert sesiones.validar(token) is None  # …pero no pasa de la duración máxima


def test_cerrar_y_listar(sesiones: RepositorioSesiones, reloj: Reloj) -> None:
    t1, s1 = sesiones.crear(1, "ip1", "a")
    reloj.ahora += 1
    _, s2 = sesiones.crear(1, "ip2", "b")
    reloj.ahora += 1
    _, s3 = sesiones.crear(1, "ip3", "c")
    _, ajena = sesiones.crear(2, "ip", "x")
    assert tuple(s.id for s in sesiones.activas(1)) == (s3.id, s2.id, s1.id)
    assert not sesiones.cerrar(1, ajena.id)  # no puede cerrar la de otro
    assert sesiones.cerrar(1, s2.id)
    assert sesiones.cerrar_todas(1, excepto=s1.id) == 1
    assert tuple(s.id for s in sesiones.activas(1)) == (s1.id,)
    assert sesiones.cerrar_token(t1)
    assert sesiones.validar(t1) is None
    assert sesiones.activas(2).tamanio() == 1


def test_desafios(sesiones: RepositorioSesiones, reloj: Reloj) -> None:
    token = sesiones.crear_desafio(1)
    assert sesiones.usuario_del_desafio(token) == 1
    for _ in range(INTENTOS_DESAFIO):
        sesiones.fallo_en_desafio(token)
    assert sesiones.usuario_del_desafio(token) is None  # agotó los intentos
    otro = sesiones.crear_desafio(1)
    reloj.ahora += DURACION_DESAFIO
    assert sesiones.usuario_del_desafio(otro) is None  # venció
    tercero = sesiones.crear_desafio(1)
    sesiones.borrar_desafio(tercero)
    assert sesiones.usuario_del_desafio(tercero) is None
    sesiones.limpiar_vencidos()
