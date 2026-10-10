"""Códigos de respaldo para entrar si se pierde el teléfono con la app de 2FA.

Se generan 10 al activar la verificación en dos pasos y se muestran una sola
vez. Cada uno sirve una vez. Se guardan con hash, igual que los tokens.
"""

import secrets

from bitcoinai.estructuras import Lista
from bitcoinai.seguridad.tokens import hash_token

CANTIDAD = 10
ALFABETO = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
"""Sin 0/O ni 1/I/L, que se confunden al copiarlos a mano."""


def generar_codigos(cantidad: int = CANTIDAD) -> Lista[str]:
    """Códigos con formato ``XXXXX-XXXXX`` (50 bits cada uno)."""
    codigos: Lista[str] = Lista()
    while codigos.tamanio() < cantidad:
        texto = "".join(secrets.choice(ALFABETO) for _ in range(10))
        codigo = f"{texto[:5]}-{texto[5:]}"
        if not _contiene(codigos, codigo):
            codigos.agregar(codigo)
    return codigos


def _contiene(codigos: Lista[str], codigo: str) -> bool:
    return any(c == codigo for c in codigos)


def normalizar_codigo(codigo: str) -> str:
    """Mayúsculas y sin espacios ni guiones, para aceptar "abcde fghij" o "ABCDE-FGHIJ"."""
    return codigo.upper().replace("-", "").replace(" ", "")


def hash_codigo(codigo: str) -> bytes:
    return hash_token(normalizar_codigo(codigo))
