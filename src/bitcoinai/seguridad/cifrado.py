"""Cifrado de datos personales (correo, documento, teléfono, secreto 2FA).

- **Cifrar (AES-256-GCM):** el dato guardado no se puede leer sin la clave, y
  cualquier alteración se detecta al descifrar. Cada valor lleva un *nonce*
  aleatorio, así el mismo correo cifrado dos veces da resultados distintos.
- **Índice ciego (HMAC-SHA256):** para buscar "¿existe este correo?" sin
  descifrar toda la tabla, se guarda además un HMAC del valor. Es determinista
  (mismo valor → mismo índice) pero no revela el dato sin la clave.

Cada uso tiene su *contexto* ("usuarios.correo"…): el cifrado lo autentica como
dato asociado, así un valor no puede copiarse a otra columna sin que se note.

De la clave maestra se derivan (HKDF) dos claves distintas, una para cifrar y
otra para los índices: si una se expusiera, la otra seguiría protegida.
"""

import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

LONGITUD_CLAVE = 32
"""Bytes de la clave maestra (256 bits)."""

_VERSION = b"\x01"
_LONGITUD_NONCE = 12


class DatoCorruptoError(Exception):
    """El valor cifrado fue alterado, es de otro contexto o se cifró con otra clave."""


def _derivar(clave_maestra: bytes, uso: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"bitcoinai/" + uso).derive(clave_maestra)


class Cifrador:
    """Cifra, descifra y calcula índices ciegos con una clave maestra de 32 bytes."""

    def __init__(self, clave_maestra: bytes) -> None:
        """Raises: ValueError si la clave no mide 32 bytes."""
        if len(clave_maestra) != LONGITUD_CLAVE:
            raise ValueError(f"La clave de cifrado debe tener {LONGITUD_CLAVE} bytes")
        self._aes = AESGCM(_derivar(clave_maestra, b"cifrado"))
        self._clave_indice = _derivar(clave_maestra, b"indice")

    def cifrar(self, texto: str, contexto: str) -> bytes:
        """``versión (1) + nonce (12) + texto cifrado con etiqueta (16)``."""
        nonce = os.urandom(_LONGITUD_NONCE)
        return _VERSION + nonce + self._aes.encrypt(nonce, texto.encode("utf-8"), contexto.encode("utf-8"))

    def descifrar(self, dato: bytes, contexto: str) -> str:
        """Raises: DatoCorruptoError si el dato no es auténtico."""
        if len(dato) < 1 + _LONGITUD_NONCE + 16 or dato[:1] != _VERSION:
            raise DatoCorruptoError("Formato de dato cifrado desconocido")
        nonce, cifrado = dato[1:1 + _LONGITUD_NONCE], dato[1 + _LONGITUD_NONCE:]
        try:
            return self._aes.decrypt(nonce, cifrado, contexto.encode("utf-8")).decode("utf-8")
        except InvalidTag as error:
            raise DatoCorruptoError("El dato cifrado fue alterado o no corresponde a esta clave") from error

    def indice(self, texto: str, contexto: str) -> bytes:
        """HMAC-SHA256 del valor (ya normalizado por quien llama) en su contexto."""
        mensaje = contexto.encode("utf-8") + b"\x00" + texto.encode("utf-8")
        return hmac.new(self._clave_indice, mensaje, hashlib.sha256).digest()
