"""Códigos de 6 dígitos que cambian cada 30 s (TOTP, RFC 6238), como Google Authenticator.

Cómo funciona: la app y el servidor comparten un secreto (se pasa una sola vez
con un código QR). Cada 30 s ambos calculan HMAC-SHA1(secreto, número de periodo)
y lo reducen a 6 dígitos (RFC 4226). Si coinciden, quien escribe el código tiene
el teléfono. Sin internet ni SMS: es gratis.
"""

import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote, urlencode

PERIODO = 30
DIGITOS = 6
VENTANA = 1
"""Periodos de tolerancia antes y después (relojes desfasados unos segundos)."""

EMISOR = "BitcoinAI"


def generar_secreto() -> str:
    """Secreto nuevo: 20 bytes al azar (160 bits) en base32, como lo piden las apps."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _bytes_secreto(secreto: str) -> bytes:
    limpio = secreto.replace(" ", "").upper()
    return base64.b32decode(limpio + "=" * (-len(limpio) % 8))


def codigo_hotp(secreto: str, contador: int, digitos: int = DIGITOS) -> str:
    """Código para un contador (RFC 4226): HMAC-SHA1 y "truncamiento dinámico"."""
    resumen = hmac.new(_bytes_secreto(secreto), struct.pack(">Q", contador), hashlib.sha1).digest()
    desplazamiento = resumen[-1] & 0x0F
    numero = struct.unpack(">I", resumen[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF
    return str(numero % 10**digitos).zfill(digitos)


def paso(momento_segundos: float, periodo: int = PERIODO) -> int:
    """Número de periodo de 30 s desde 1970."""
    return int(momento_segundos // periodo)


def verificar(secreto: str, codigo: str, momento_segundos: float, ultimo_paso_usado: int | None = None,
              ventana: int = VENTANA) -> int | None:
    """Comprueba un código.

    Un código ya usado no vale de nuevo (si alguien lo ve por encima del hombro,
    no le sirve): solo se aceptan pasos posteriores a ``ultimo_paso_usado``.

    Returns:
        El paso que coincidió (para guardarlo como último usado), o None.
    """
    limpio = codigo.replace(" ", "")
    if len(limpio) != DIGITOS or not limpio.isdigit():
        return None
    actual = paso(momento_segundos)
    for candidato in range(actual - ventana, actual + ventana + 1):
        if ultimo_paso_usado is not None and candidato <= ultimo_paso_usado:
            continue
        # compare_digest tarda lo mismo acierte o no: no da pistas por el tiempo.
        if hmac.compare_digest(codigo_hotp(secreto, candidato), limpio):
            return candidato
    return None


def uri_otpauth(secreto: str, cuenta: str, emisor: str = EMISOR) -> str:
    """Enlace ``otpauth://`` que va dentro del código QR para escanear con la app."""
    etiqueta = quote(f"{emisor}:{cuenta}", safe="")
    parametros = urlencode({"secret": secreto, "issuer": emisor, "algorithm": "SHA1",
                            "digits": DIGITOS, "period": PERIODO})
    return f"otpauth://totp/{etiqueta}?{parametros}"
