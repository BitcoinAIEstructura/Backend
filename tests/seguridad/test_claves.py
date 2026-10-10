import base64
from pathlib import Path

import pytest

from bitcoinai.seguridad.claves import ARCHIVO_CLAVE, cargar_clave, decodificar_clave, generar_clave_texto


def test_generar_y_decodificar() -> None:
    texto = generar_clave_texto()
    assert len(texto) == 44
    assert len(decodificar_clave(texto)) == 32
    assert generar_clave_texto() != texto


def test_acepta_base64_normal_y_url() -> None:
    clave = bytes(range(250, 256)) + bytes(26)
    assert decodificar_clave(base64.b64encode(clave).decode()) == clave
    assert decodificar_clave(base64.urlsafe_b64encode(clave).decode().rstrip("=")) == clave


@pytest.mark.parametrize("mala", ["no-es-base64-%%%", base64.b64encode(b"corta").decode()])
def test_clave_invalida(mala: str) -> None:
    with pytest.raises(ValueError, match="CLAVE_CIFRADO"):
        decodificar_clave(mala)


def test_usa_la_variable_de_entorno(tmp_path: Path) -> None:
    texto = generar_clave_texto()
    assert cargar_clave(tmp_path, {"CLAVE_CIFRADO": texto}) == decodificar_clave(texto)
    assert not (tmp_path / ARCHIVO_CLAVE).exists()


def test_sin_variable_genera_un_archivo_y_lo_reutiliza(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    primera = cargar_clave(tmp_path / "datos", {})
    assert (tmp_path / "datos" / ARCHIVO_CLAVE).exists()
    assert "CLAVE_CIFRADO" in caplog.text
    assert cargar_clave(tmp_path / "datos", {}) == primera
