import pytest

from bitcoinai.seguridad.contrasenas import HashContrasenas, ParametrosArgon2
from bitcoinai.usuarios.actividad import TipoActividad
from bitcoinai.usuarios.servicio import (
    Cliente,
    CredencialesInvalidasError,
    DemasiadosIntentosError,
)
from tests.usuarios.entorno import CLIENTE, CONTRASENA, crear_entorno, datos


def test_inicio_correcto_sin_dos_pasos() -> None:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    resultado = e.servicio.iniciar_sesion("  ANA@correo.co ", CONTRASENA, CLIENTE)
    assert resultado.usuario is not None and resultado.usuario.correo == "ana@correo.co"
    assert resultado.token_sesion is not None and resultado.token_desafio is None
    assert e.servicio.sesiones.validar(resultado.token_sesion) is not None


@pytest.mark.parametrize(("correo", "contrasena"), [
    ("ana@correo.co", "Otra-Clave-2026"), ("nadie@correo.co", CONTRASENA), ("no-es-correo", CONTRASENA),
])
def test_mismo_mensaje_si_falla_el_correo_o_la_contrasena(correo: str, contrasena: str) -> None:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    with pytest.raises(CredencialesInvalidasError, match="^Correo o contraseña incorrectos$"):
        e.servicio.iniciar_sesion(correo, contrasena, CLIENTE)


def test_bloqueo_tras_cinco_fallos_y_desbloqueo_a_los_quince_minutos() -> None:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    for _ in range(5):
        with pytest.raises(CredencialesInvalidasError):
            e.servicio.iniciar_sesion("ana@correo.co", "mala", CLIENTE)
    with pytest.raises(DemasiadosIntentosError, match="15 minutos"):
        e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE)  # ni con la correcta
    fallidos = [a for a in e.servicio.actividad.recientes(1) if a.tipo is TipoActividad.INICIO_FALLIDO]
    assert len(fallidos) == 5
    e.reloj.ahora += 15 * 60
    assert e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE).token_sesion is not None


def test_el_bloqueo_tambien_aplica_a_correos_inexistentes() -> None:
    e = crear_entorno()
    for _ in range(5):
        with pytest.raises(CredencialesInvalidasError):
            e.servicio.iniciar_sesion("nadie@correo.co", "x", CLIENTE)
    with pytest.raises(DemasiadosIntentosError):
        e.servicio.iniciar_sesion("nadie@correo.co", "x", CLIENTE)


def test_limite_por_ip_con_correos_distintos() -> None:
    e = crear_entorno()
    for n in range(20):
        with pytest.raises(CredencialesInvalidasError):
            e.servicio.iniciar_sesion(f"u{n}@correo.co", "x", CLIENTE)
    with pytest.raises(DemasiadosIntentosError):
        e.servicio.iniciar_sesion("u99@correo.co", "x", CLIENTE)
    with pytest.raises(CredencialesInvalidasError):
        e.servicio.iniciar_sesion("u99@correo.co", "x", Cliente("10.9.9.9", "otro"))


def test_un_acierto_reinicia_los_fallos_del_correo() -> None:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    for _ in range(4):
        with pytest.raises(CredencialesInvalidasError):
            e.servicio.iniciar_sesion("ana@correo.co", "mala", CLIENTE)
    e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE)
    for _ in range(4):
        with pytest.raises(CredencialesInvalidasError):
            e.servicio.iniciar_sesion("ana@correo.co", "mala", CLIENTE)


def test_hash_viejo_se_fortalece_al_entrar() -> None:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    e.servicio._hasher = HashContrasenas(ParametrosArgon2(iteraciones=2, memoria_kib=16, paralelismo=1))
    viejo = e.servicio.usuarios.credenciales(1)
    e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE)
    nuevo = e.servicio.usuarios.credenciales(1)
    assert viejo is not None and nuevo is not None
    assert nuevo.contrasena_hash != viejo.contrasena_hash and "t=2" in nuevo.contrasena_hash
