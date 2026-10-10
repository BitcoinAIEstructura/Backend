import pytest

from bitcoinai.seguridad import totp
from bitcoinai.usuarios.actividad import TipoActividad
from bitcoinai.usuarios.servicio import (
    CodigoInvalidoError,
    CredencialesInvalidasError,
    DemasiadosIntentosError,
    DesafioVencidoError,
    OperacionCuentaError,
)
from tests.usuarios.entorno import CLIENTE, CONTRASENA, Entorno, crear_entorno, datos


def codigo_actual(e: Entorno, secreto: str, desfase: int = 0) -> str:
    return totp.codigo_hotp(secreto, totp.paso(e.reloj.ahora) + desfase)


def con_dos_pasos() -> tuple[Entorno, str, tuple[str, ...]]:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    config = e.servicio.iniciar_dos_pasos(1)
    codigos = tuple(e.servicio.confirmar_dos_pasos(1, codigo_actual(e, config.secreto), CLIENTE))
    e.reloj.ahora += 30  # el código usado para activar ya no vale
    return e, config.secreto, codigos


def test_activar() -> None:
    e = crear_entorno()
    e.servicio.registrar(datos(), CLIENTE)
    config = e.servicio.iniciar_dos_pasos(1)
    assert config.uri.startswith("otpauth://totp/BitcoinAI%3Aana%40correo.co?secret=" + config.secreto)
    with pytest.raises(CodigoInvalidoError):
        e.servicio.confirmar_dos_pasos(1, "000000", CLIENTE)
    codigos = e.servicio.confirmar_dos_pasos(1, codigo_actual(e, config.secreto), CLIENTE)
    assert codigos.tamanio() == 10
    usuario = e.servicio.usuarios.por_id(1)
    assert usuario is not None and usuario.verificacion_dos_pasos
    with pytest.raises(OperacionCuentaError, match="ya está activa"):
        e.servicio.iniciar_dos_pasos(1)
    assert e.servicio.actividad.recientes(1).primero().tipo is TipoActividad.DOS_PASOS_ACTIVADA


def test_inicio_de_sesion_en_dos_pasos() -> None:
    e, secreto, _ = con_dos_pasos()
    resultado = e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE)
    assert resultado.token_sesion is None and resultado.token_desafio is not None
    usuario, token = e.servicio.completar_segundo_paso(resultado.token_desafio, codigo_actual(e, secreto), CLIENTE)
    assert usuario.id == 1 and e.servicio.sesiones.validar(token) is not None
    with pytest.raises(DesafioVencidoError):  # el desafío ya se usó
        e.servicio.completar_segundo_paso(resultado.token_desafio, codigo_actual(e, secreto), CLIENTE)


def test_el_mismo_codigo_no_sirve_dos_veces() -> None:
    e, secreto, _ = con_dos_pasos()
    codigo = codigo_actual(e, secreto)
    desafio = e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE).token_desafio
    assert desafio is not None
    e.servicio.completar_segundo_paso(desafio, codigo, CLIENTE)
    otro = e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE).token_desafio
    assert otro is not None
    with pytest.raises(CodigoInvalidoError):
        e.servicio.completar_segundo_paso(otro, codigo, CLIENTE)


def test_codigo_de_respaldo_de_un_solo_uso() -> None:
    e, _, codigos = con_dos_pasos()
    for esperado_ok in (True, False):
        desafio = e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE).token_desafio
        assert desafio is not None
        if esperado_ok:
            e.servicio.completar_segundo_paso(desafio, codigos[0].lower(), CLIENTE)
        else:
            with pytest.raises(CodigoInvalidoError):
                e.servicio.completar_segundo_paso(desafio, codigos[0], CLIENTE)
    assert any(a.tipo is TipoActividad.CODIGO_RESPALDO_USADO and a.detalle == "Quedan 9"
               for a in e.servicio.actividad.recientes(1))


def test_el_desafio_se_agota_tras_cinco_codigos_malos() -> None:
    e, secreto, _ = con_dos_pasos()
    desafio = e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE).token_desafio
    assert desafio is not None
    for _ in range(5):
        with pytest.raises(CodigoInvalidoError):
            e.servicio.completar_segundo_paso(desafio, "000000", CLIENTE)
    with pytest.raises(DesafioVencidoError):
        e.servicio.completar_segundo_paso(desafio, codigo_actual(e, secreto), CLIENTE)


def test_desactivar_pide_contrasena_y_codigo() -> None:
    e, secreto, codigos = con_dos_pasos()
    with pytest.raises(CredencialesInvalidasError):
        e.servicio.desactivar_dos_pasos(1, "mala", codigo_actual(e, secreto), CLIENTE)
    with pytest.raises(CodigoInvalidoError):
        e.servicio.desactivar_dos_pasos(1, CONTRASENA, "000000", CLIENTE)
    e.servicio.desactivar_dos_pasos(1, CONTRASENA, codigos[3], CLIENTE)
    assert e.servicio.usuarios.codigos_restantes(1) == 0
    assert e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE).token_sesion is not None
    with pytest.raises(OperacionCuentaError, match="no está activa"):
        e.servicio.desactivar_dos_pasos(1, CONTRASENA, "000000", CLIENTE)


def test_regenerar_codigos_invalida_los_anteriores() -> None:
    e, secreto, viejos = con_dos_pasos()
    nuevos = tuple(e.servicio.regenerar_codigos(1, codigo_actual(e, secreto), CLIENTE))
    assert set(nuevos).isdisjoint(viejos)
    desafio = e.servicio.iniciar_sesion("ana@correo.co", CONTRASENA, CLIENTE).token_desafio
    assert desafio is not None
    with pytest.raises(CodigoInvalidoError):
        e.servicio.completar_segundo_paso(desafio, viejos[1], CLIENTE)
    e.servicio.completar_segundo_paso(desafio, nuevos[1], CLIENTE)


def test_limite_de_codigos_malos_con_la_sesion_abierta() -> None:
    e, _, _ = con_dos_pasos()
    for _ in range(5):
        with pytest.raises(CodigoInvalidoError):
            e.servicio.regenerar_codigos(1, "000000", CLIENTE)
    with pytest.raises(DemasiadosIntentosError):
        e.servicio.regenerar_codigos(1, "000000", CLIENTE)
