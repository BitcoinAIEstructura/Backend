"""Reglas para que una contraseña sea difícil de adivinar."""

import unicodedata

from bitcoinai.estructuras import Lista

LONGITUD_MINIMA = 10
LONGITUD_MAXIMA = 128  # Argon2 acepta más, pero un límite evita abusos con textos enormes

COMUNES = frozenset({
    "contraseña", "contrasena", "password", "passw0rd", "123456789", "1234567890", "qwertyuiop",
    "bitcoin", "bitcoin123", "colombia", "administrador", "admin12345", "iloveyou", "tequiero",
    "abc1234567", "aaaaaaaaaa", "contraseña1", "password123", "qwerty123", "1q2w3e4r5t",
})
"""Contraseñas (o raíces) tan comunes que nunca se aceptan, aunque cumplan lo demás."""

SECUENCIAS = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "qwertyuiop", "asdfghjkl", "zxcvbnm")


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar "Contraseña" con "contrasena"."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).casefold()


def _clases(contrasena: str) -> int:
    """Cuántos tipos de carácter usa: minúsculas, mayúsculas, dígitos y símbolos."""
    return sum((
        any(c.islower() for c in contrasena),
        any(c.isupper() for c in contrasena),
        any(c.isdigit() for c in contrasena),
        any(not c.isalnum() for c in contrasena),
    ))


def _es_secuencia_o_repeticion(normal: str) -> bool:
    if len(set(normal)) <= 2:
        return True
    return any(normal in s or normal in s[::-1] for s in SECUENCIAS)


def problemas_contrasena(contrasena: str, datos_personales: tuple[str, ...] = ()) -> Lista[str]:
    """Qué le falta a la contraseña para ser aceptada (vacía si está bien).

    Args:
        contrasena: la contraseña propuesta.
        datos_personales: nombre, apellido, correo, documento…; la contraseña no
            puede contenerlos (es lo primero que prueba un atacante).
    """
    problemas: Lista[str] = Lista()
    if len(contrasena) < LONGITUD_MINIMA:
        problemas.agregar(f"Debe tener al menos {LONGITUD_MINIMA} caracteres")
    if len(contrasena) > LONGITUD_MAXIMA:
        problemas.agregar(f"Debe tener como máximo {LONGITUD_MAXIMA} caracteres")
    if _clases(contrasena) < 3:
        problemas.agregar("Debe combinar al menos 3 de estos: minúsculas, mayúsculas, números y símbolos")
    normal = _normalizar(contrasena)
    raiz = normal.rstrip("0123456789!@#$%&*.?-_ ")
    if normal in COMUNES or raiz in COMUNES or _es_secuencia_o_repeticion(normal):
        problemas.agregar("Es una contraseña demasiado común o predecible")
    for dato in datos_personales:
        for parte in _normalizar(dato).replace("@", " ").replace(".", " ").split():
            if len(parte) >= 4 and parte in normal:
                problemas.agregar("No puede contener tu nombre, correo ni documento")
                return problemas
    return problemas
