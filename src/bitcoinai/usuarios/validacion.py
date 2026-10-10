"""Validación y normalización de los datos de registro.

Cada función recibe lo que escribió el usuario, lo limpia (espacios, puntos…) y
devuelve la forma canónica que se guarda, o lanza ``DatoInvalidoError`` con un
mensaje en español que se puede mostrar tal cual.
"""

import re
from enum import Enum


class DatoInvalidoError(ValueError):
    """Un dato del formulario no es válido. ``campo`` dice cuál (en camelCase, como en la API)."""

    def __init__(self, campo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.campo = campo
        self.mensaje = mensaje


class TipoDocumento(Enum):
    """Documentos aceptados."""

    CC = "Cédula de ciudadanía"
    CE = "Cédula de extranjería"


_CC = re.compile(r"[1-9]\d{4,9}")
_CE = re.compile(r"[A-Z0-9]{5,12}")


def normalizar_documento(tipo: TipoDocumento, numero: str) -> str:
    """Cédula sin puntos, espacios ni guiones ("1.023.456.789" → "1023456789").

    - **CC:** solo números, de 5 a 10 dígitos, sin cero inicial.
    - **CE:** de 5 a 12 caracteres, números y letras (las más nuevas pueden llevar letras).
    """
    limpio = re.sub(r"[\s.\-]", "", numero).upper()
    if tipo is TipoDocumento.CC and not _CC.fullmatch(limpio):
        raise DatoInvalidoError("numeroDocumento",
                                "La cédula de ciudadanía debe tener entre 5 y 10 dígitos, sin letras")
    if tipo is TipoDocumento.CE and not _CE.fullmatch(limpio):
        raise DatoInvalidoError("numeroDocumento",
                                "La cédula de extranjería debe tener entre 5 y 12 letras o números")
    return limpio


def leer_tipo_documento(texto: str) -> TipoDocumento:
    try:
        return TipoDocumento[texto.strip().upper()]
    except KeyError:
        raise DatoInvalidoError("tipoDocumento", "El tipo de documento debe ser CC o CE") from None


_CELULAR_COLOMBIA = re.compile(r"3\d{9}")
_INTERNACIONAL = re.compile(r"\+[1-9]\d{7,14}")


def normalizar_telefono(telefono: str) -> str:
    """Teléfono en formato internacional E.164 ("+573001234567").

    - Un celular colombiano de 10 dígitos que empieza por 3 se acepta sin indicativo
      ("300 123 4567" → "+573001234567").
    - Cualquier otro número debe llevar el indicativo del país con "+" (de 8 a 15 dígitos).
    """
    limpio = re.sub(r"[\s.\-()]", "", telefono)
    if limpio.startswith("00"):
        limpio = "+" + limpio[2:]
    if _CELULAR_COLOMBIA.fullmatch(limpio):
        return "+57" + limpio
    if _INTERNACIONAL.fullmatch(limpio):
        if limpio.startswith("+57") and not _CELULAR_COLOMBIA.fullmatch(limpio[3:]):
            raise DatoInvalidoError("telefono", "Un celular colombiano tiene 10 dígitos y empieza por 3")
        return limpio
    raise DatoInvalidoError("telefono",
                            "Escribe un celular colombiano de 10 dígitos o un número con indicativo (+57, +1…)")


_CORREO = re.compile(r"[a-z0-9._%+\-]{1,64}@(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}")
_NOMBRE = re.compile(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*")


def normalizar_correo(correo: str) -> str:
    """Correo en minúsculas y sin espacios alrededor; máximo 254 caracteres."""
    limpio = correo.strip().lower()
    if len(limpio) > 254 or not _CORREO.fullmatch(limpio) or ".." in limpio:
        raise DatoInvalidoError("correo", "El correo no es válido")
    return limpio


def normalizar_nombre(texto: str, campo: str = "nombre") -> str:
    """Nombre o apellido: letras (con tildes y ñ), espacios, apóstrofo o guion; de 2 a 50 caracteres.

    Los espacios repetidos se reducen a uno ("María   José" → "María José").
    """
    limpio = " ".join(texto.split())
    que = "El nombre" if campo == "nombre" else "El apellido"
    if not 2 <= len(limpio) <= 50:
        raise DatoInvalidoError(campo, f"{que} debe tener entre 2 y 50 caracteres")
    if not _NOMBRE.fullmatch(limpio):
        raise DatoInvalidoError(campo, f"{que} solo puede tener letras, espacios, apóstrofo o guion")
    return limpio
