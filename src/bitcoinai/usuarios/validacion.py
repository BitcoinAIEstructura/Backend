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
