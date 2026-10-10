import pytest

from bitcoinai.usuarios.actividad import TipoActividad
from bitcoinai.usuarios.servicio import (
    Cliente,
    CredencialesInvalidasError,
    OperacionCuentaError,
    SesionInvalidaError,
)
from bitcoinai.usuarios.validacion import DatoInvalidoError
from tests.usuarios.entorno import CLIENTE, CONTRASENA, Entorno, crear_entorno, datos


def entrar(e: Entorno, contrasena: str = CONTRASENA, ip: str = "127.0.0.1") -> str:
    token = e.servicio.iniciar_sesion("ana@correo.co", contrasena, Cliente(ip, "nav")).token_sesion
    assert token is not None
    return token


def test_sesion_actual_y_cerrar() -> None:
    e = crear_entorno()
    _, token = e.servicio.registrar(datos(), CLIENTE)
    usuario, sesion = e.servicio.sesion_actual(token)
    assert usuario.correo == "ana@correo.co" and sesion.usuario_id == usuario.id
    e.servicio.cerrar_sesion(token, CLIENTE)
    for malo in (token, None, "", "inventado"):
        with pytest.raises(SesionInvalidaError, match="vuelve a iniciar sesión"):
            e.servicio.sesion_actual(malo)
    assert e.servicio.actividad_reciente(1).primero().tipo is TipoActividad.CIERRE_SESION


def test_ver_y_cerrar_sesiones_de_otros_dispositivos() -> None:
    e = crear_entorno()
    _, actual = e.servicio.registrar(datos(), CLIENTE)
    otro = entrar(e, ip="10.0.0.2")
    entrar(e, ip="10.0.0.3")
    _, sesion_actual = e.servicio.sesion_actual(actual)
    _, sesion_otro = e.servicio.sesion_actual(otro)
    assert e.servicio.sesiones_activas(1).tamanio() == 3
    e.servicio.cerrar_otra_sesion(1, sesion_otro.id, CLIENTE)
    with pytest.raises(OperacionCuentaError):
        e.servicio.cerrar_otra_sesion(1, sesion_otro.id, CLIENTE)
    assert e.servicio.cerrar_otras_sesiones(1, sesion_actual.id, CLIENTE) == 1
    assert tuple(s.id for s in e.servicio.sesiones_activas(1)) == (sesion_actual.id,)


def test_cambiar_contrasena_cierra_las_demas_sesiones() -> None:
    e = crear_entorno()
    _, actual = e.servicio.registrar(datos(), CLIENTE)
    otro = entrar(e)
    _, sesion = e.servicio.sesion_actual(actual)
    e.servicio.cambiar_contrasena(1, CONTRASENA, "Sol-Azul-Brillante-9", sesion.id, CLIENTE)
    e.servicio.sesion_actual(actual)  # la actual sigue abierta
    with pytest.raises(SesionInvalidaError):
        e.servicio.sesion_actual(otro)
    with pytest.raises(CredencialesInvalidasError):
        entrar(e)
    entrar(e, "Sol-Azul-Brillante-9")


@pytest.mark.parametrize(("actual", "nueva", "error"), [
    ("mala", "Sol-Azul-Brillante-9", CredencialesInvalidasError),
    (CONTRASENA, CONTRASENA, DatoInvalidoError),
    (CONTRASENA, "corta", DatoInvalidoError),
    (CONTRASENA, "Perez-Brillante-9", DatoInvalidoError),
])
def test_cambio_de_contrasena_rechazado(actual: str, nueva: str, error: type[Exception]) -> None:
    e = crear_entorno()
    _, token = e.servicio.registrar(datos(), CLIENTE)
    _, sesion = e.servicio.sesion_actual(token)
    with pytest.raises(error):
        e.servicio.cambiar_contrasena(1, actual, nueva, sesion.id, CLIENTE)
