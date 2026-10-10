import os

import pytest

from bitcoinai.seguridad.cifrado import Cifrador, DatoCorruptoError

CLAVE = bytes(range(32))


@pytest.fixture
def cifrador() -> Cifrador:
    return Cifrador(CLAVE)


def test_ida_y_vuelta(cifrador: Cifrador) -> None:
    dato = cifrador.cifrar("santiago@correo.co", "usuarios.correo")
    assert b"santiago" not in dato
    assert cifrador.descifrar(dato, "usuarios.correo") == "santiago@correo.co"
    assert cifrador.descifrar(cifrador.cifrar("ñandú ✓", "x"), "x") == "ñandú ✓"


def test_mismo_valor_cifrado_dos_veces_es_distinto(cifrador: Cifrador) -> None:
    assert cifrador.cifrar("3001234567", "t") != cifrador.cifrar("3001234567", "t")


def test_detecta_alteraciones(cifrador: Cifrador) -> None:
    dato = bytearray(cifrador.cifrar("1023456789", "usuarios.documento"))
    dato[-1] ^= 1
    with pytest.raises(DatoCorruptoError):
        cifrador.descifrar(bytes(dato), "usuarios.documento")


def test_otro_contexto_u_otra_clave_no_descifran(cifrador: Cifrador) -> None:
    dato = cifrador.cifrar("1023456789", "usuarios.documento")
    with pytest.raises(DatoCorruptoError):
        cifrador.descifrar(dato, "usuarios.telefono")
    with pytest.raises(DatoCorruptoError):
        Cifrador(os.urandom(32)).descifrar(dato, "usuarios.documento")
    with pytest.raises(DatoCorruptoError):
        cifrador.descifrar(b"\x02basura", "usuarios.documento")


def test_indice_ciego_determinista_y_por_contexto(cifrador: Cifrador) -> None:
    a = cifrador.indice("ana@correo.co", "usuarios.correo")
    assert a == cifrador.indice("ana@correo.co", "usuarios.correo")
    assert len(a) == 32
    assert a != cifrador.indice("ana@correo.co", "usuarios.documento")
    assert a != Cifrador(os.urandom(32)).indice("ana@correo.co", "usuarios.correo")


def test_clave_de_largo_invalido() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        Cifrador(b"corta")
