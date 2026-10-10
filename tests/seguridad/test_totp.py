import base64

import pytest

from bitcoinai.seguridad import totp

# Secreto de los vectores de prueba oficiales del RFC 6238 (ASCII "12345678901234567890").
SECRETO_RFC = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(("momento", "esperado"), [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
])
def test_vectores_oficiales_rfc_6238(momento: int, esperado: str) -> None:
    assert totp.codigo_hotp(SECRETO_RFC, totp.paso(momento), digitos=8) == esperado


def test_vectores_rfc_4226() -> None:
    esperados = ("755224", "287082", "359152", "969429", "338314")
    assert tuple(totp.codigo_hotp(SECRETO_RFC, c) for c in range(5)) == esperados


def test_secreto_nuevo() -> None:
    secreto = totp.generar_secreto()
    assert len(secreto) == 32 and secreto.isalnum() and secreto.isupper()
    assert totp.generar_secreto() != secreto


def test_verificar_con_tolerancia_de_un_periodo() -> None:
    secreto = totp.generar_secreto()
    ahora = 1_800_000_000
    actual = totp.codigo_hotp(secreto, totp.paso(ahora))
    anterior = totp.codigo_hotp(secreto, totp.paso(ahora) - 1)
    viejo = totp.codigo_hotp(secreto, totp.paso(ahora) - 3)
    assert totp.verificar(secreto, actual, ahora) == totp.paso(ahora)
    assert totp.verificar(secreto, anterior, ahora) == totp.paso(ahora) - 1
    assert totp.verificar(secreto, viejo, ahora) is None
    assert totp.verificar(secreto, actual[:3] + " " + actual[3:], ahora) is not None  # admite espacio


def test_un_codigo_no_se_puede_reutilizar() -> None:
    secreto = totp.generar_secreto()
    ahora = 1_800_000_000
    codigo = totp.codigo_hotp(secreto, totp.paso(ahora))
    usado = totp.verificar(secreto, codigo, ahora)
    assert usado is not None
    assert totp.verificar(secreto, codigo, ahora + 5, ultimo_paso_usado=usado) is None


@pytest.mark.parametrize("malo", ["", "12345", "1234567", "abcdef", "12 34 5"])
def test_formato_invalido(malo: str) -> None:
    assert totp.verificar(totp.generar_secreto(), malo, 1_800_000_000) is None


def test_uri_para_el_codigo_qr() -> None:
    uri = totp.uri_otpauth("JBSWY3DPEHPK3PXP", "ana@correo.co")
    assert uri.startswith("otpauth://totp/BitcoinAI%3Aana%40correo.co?")
    assert "secret=JBSWY3DPEHPK3PXP" in uri and "issuer=BitcoinAI" in uri
    assert "digits=6" in uri and "period=30" in uri
