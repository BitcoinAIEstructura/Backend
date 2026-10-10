import pytest

from bitcoinai.usuarios.modelo import DatosRegistro, Usuario, enmascarar
from bitcoinai.usuarios.validacion import DatoInvalidoError, TipoDocumento

VALIDOS = {
    "nombre": " Santiago ", "apellido": "Argoti", "correo": "Santi@Correo.CO", "tipo_documento": "cc",
    "numero_documento": "1.023.456.789", "telefono": "300 123 4567", "contrasena": "Luna-Roja-2026",
}


def test_valida_y_normaliza_todo() -> None:
    datos = DatosRegistro.validar(**VALIDOS)
    assert (datos.nombre, datos.correo, datos.tipo_documento, datos.numero_documento, datos.telefono) == (
        "Santiago", "santi@correo.co", TipoDocumento.CC, "1023456789", "+573001234567")


@pytest.mark.parametrize(("campo", "valor", "campo_error"), [
    ("correo", "malo", "correo"),
    ("tipo_documento", "TI", "tipoDocumento"),
    ("numero_documento", "12", "numeroDocumento"),
    ("telefono", "123", "telefono"),
    ("apellido", "4rgoti", "apellido"),
    ("contrasena", "corta", "contrasena"),
    ("contrasena", "Santiago-2026!", "contrasena"),  # contiene el nombre
])
def test_cada_campo_invalido_se_reporta_con_su_nombre(campo: str, valor: str, campo_error: str) -> None:
    with pytest.raises(DatoInvalidoError) as error:
        DatosRegistro.validar(**{**VALIDOS, campo: valor})
    assert error.value.campo == campo_error


def test_enmascarar() -> None:
    assert enmascarar("1023456789") == "******6789"
    assert enmascarar("123") == "***"
    usuario = Usuario(1, "Ana", "Pérez", "ana@correo.co", TipoDocumento.CE, "E12345A", "+573001234567", False, 0)
    assert usuario.documento_enmascarado == "***345A"
    assert usuario.telefono_enmascarado == "+57******4567"
