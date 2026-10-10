import pytest

from bitcoinai.usuarios.validacion import (
    DatoInvalidoError,
    TipoDocumento,
    leer_tipo_documento,
    normalizar_documento,
    normalizar_telefono,
)

CC, CE = TipoDocumento.CC, TipoDocumento.CE


@pytest.mark.parametrize(("escrito", "esperado"), [
    ("1023456789", "1023456789"), ("1.023.456.789", "1023456789"), (" 79 123 456 ", "79123456"), ("12345", "12345"),
])
def test_cedula_de_ciudadania_valida(escrito: str, esperado: str) -> None:
    assert normalizar_documento(CC, escrito) == esperado


@pytest.mark.parametrize("malo", ["", "1234", "12345678901", "0123456789", "10234A6789"])
def test_cedula_de_ciudadania_invalida(malo: str) -> None:
    with pytest.raises(DatoInvalidoError) as error:
        normalizar_documento(CC, malo)
    assert error.value.campo == "numeroDocumento"
    assert "cédula de ciudadanía" in error.value.mensaje


@pytest.mark.parametrize(("escrito", "esperado"), [("654321", "654321"), ("e-12345a", "E12345A")])
def test_cedula_de_extranjeria_valida(escrito: str, esperado: str) -> None:
    assert normalizar_documento(CE, escrito) == esperado


@pytest.mark.parametrize("malo", ["1234", "ABCDEFGHIJKLM", "12#456"])
def test_cedula_de_extranjeria_invalida(malo: str) -> None:
    with pytest.raises(DatoInvalidoError, match="extranjería"):
        normalizar_documento(CE, malo)


def test_tipo_de_documento() -> None:
    assert leer_tipo_documento(" cc ") is CC
    assert leer_tipo_documento("CE") is CE
    with pytest.raises(DatoInvalidoError, match="CC o CE"):
        leer_tipo_documento("PASAPORTE")


@pytest.mark.parametrize(("escrito", "esperado"), [
    ("3001234567", "+573001234567"),
    ("300 123 4567", "+573001234567"),
    ("+57 300-123-4567", "+573001234567"),
    ("0057 3001234567", "+573001234567"),
    ("+1 (305) 555-0123", "+13055550123"),
    ("+34 612 345 678", "+34612345678"),
])
def test_telefono_valido(escrito: str, esperado: str) -> None:
    assert normalizar_telefono(escrito) == esperado


@pytest.mark.parametrize("malo", ["", "12345", "6012345678", "+57 601 234 5678", "+0123456789", "300123456a"])
def test_telefono_invalido(malo: str) -> None:
    with pytest.raises(DatoInvalidoError) as error:
        normalizar_telefono(malo)
    assert error.value.campo == "telefono"
