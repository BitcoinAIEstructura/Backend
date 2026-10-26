import pytest

from bitcoinai.usuarios.actividad import TipoActividad
from bitcoinai.usuarios.servicio import Cliente, DemasiadosIntentosError, RegistroRechazadoError
from tests.usuarios.entorno import CLIENTE, CONTRASENA, crear_entorno, datos


def test_registrar_crea_la_cuenta_y_abre_sesion() -> None:
    e = crear_entorno()
    usuario, token = e.servicio.registrar(datos(), CLIENTE).sesion()
    assert usuario.correo == "ana@correo.co"
    sesion = e.servicio.sesiones.validar(token)
    assert sesion is not None and sesion.usuario_id == usuario.id
    credenciales = e.servicio.usuarios.credenciales(usuario.id)
    assert credenciales is not None
    assert credenciales.contrasena_hash.startswith("$argon2id$")
    assert CONTRASENA not in credenciales.contrasena_hash
    tipos = tuple(a.tipo for a in e.servicio.actividad.recientes(usuario.id))
    assert tipos == (TipoActividad.INICIO_SESION, TipoActividad.REGISTRO)


def test_correo_o_documento_repetido() -> None:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    with pytest.raises(RegistroRechazadoError, match="Ya existe una cuenta"):
        e.servicio.registrar(datos(documento="55555555"), CLIENTE)


def test_limite_de_registros_por_ip() -> None:
    e = crear_entorno()
    for n in range(10):
        e.servicio.registrar(datos(f"u{n}@correo.co", f"1000000{n:03d}"), CLIENTE)
    with pytest.raises(DemasiadosIntentosError) as error:
        e.servicio.registrar(datos("otro@correo.co", "99999999"), CLIENTE)
    assert "minutos" in error.value.mensaje
    e.servicio.registrar(datos("otro@correo.co", "99999999"), Cliente("10.0.0.2", "x"))  # otra IP sí puede
