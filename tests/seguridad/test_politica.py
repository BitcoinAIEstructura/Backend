import pytest

from bitcoinai.seguridad.politica import problemas_contrasena


def problemas(contrasena: str, *datos: str) -> tuple[str, ...]:
    return tuple(problemas_contrasena(contrasena, datos))


@pytest.mark.parametrize("buena", ["Luna-Roja-2026", "tren azul VERDE 7", "Ñandú.Saltó#Lejos", "x9$Kp2!mQz"])
def test_contrasenas_aceptadas(buena: str) -> None:
    assert problemas(buena) == ()


def test_muy_corta() -> None:
    assert problemas("Ab1!x")[0] == "Debe tener al menos 10 caracteres"


def test_muy_larga() -> None:
    assert "Debe tener como máximo 128 caracteres" in problemas("Ab1!" * 40)


def test_pocas_clases_de_caracteres() -> None:
    assert problemas("solominusculasperolarga") == (
        "Debe combinar al menos 3 de estos: minúsculas, mayúsculas, números y símbolos",)


@pytest.mark.parametrize("comun", ["Password123!", "Contraseña1!", "Bitcoin123$$", "Qwertyuiop1!", "Aaaaaaaaaa1!"])
def test_comunes_o_predecibles(comun: str) -> None:
    assert "Es una contraseña demasiado común o predecible" in problemas(comun)


def test_no_puede_contener_datos_personales() -> None:
    mensaje = "No puede contener tu nombre, correo ni documento"
    assert mensaje in problemas("Santiago#2026x", "Santiago", "Pérez")
    assert mensaje in problemas("Perez!Segura9", "Santiago", "Pérez")  # sin tilde también
    assert mensaje in problemas("Mi-correo-santi77", "santi77@gmail.com")
    assert mensaje in problemas("Doc#1023456789", "1023456789")
    assert problemas("Ana-Luna-Roja-26", "Ana") == ()  # partes de menos de 4 letras no cuentan
