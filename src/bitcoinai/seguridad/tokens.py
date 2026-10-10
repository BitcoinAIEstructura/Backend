"""Tokens aleatorios para sesiones y desafíos.

El token viaja al navegador (en una cookie) y en la base solo se guarda su hash
SHA-256. Si alguien copiara la base, no podría usar ninguna sesión. Un token
de 256 bits al azar no se puede adivinar, así que basta un hash rápido (no hace
falta Argon2, que es para contraseñas elegidas por personas).
"""

import hashlib
import hmac
import secrets

BYTES_TOKEN = 32


def generar_token() -> str:
    """Token nuevo de 256 bits, en base64 URL (43 caracteres)."""
    return secrets.token_urlsafe(BYTES_TOKEN)


def hash_token(token: str) -> bytes:
    """SHA-256 del token: lo único que se guarda."""
    return hashlib.sha256(token.encode("utf-8")).digest()


def mismo_hash(a: bytes, b: bytes) -> bool:
    """Comparación en tiempo constante."""
    return hmac.compare_digest(a, b)
