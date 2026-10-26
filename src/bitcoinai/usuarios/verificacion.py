"""Verificación del correo al crear la cuenta: un código de 6 dígitos que llega por correo.

Como con las sesiones, en la base solo quedan hashes. El token va en una cookie HttpOnly
(así la página sabe a qué cuenta corresponde el código sin poner el correo en la URL)
y el código va al correo. Cada código sirve 15 minutos y admite 5 intentos.
"""

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from bitcoinai.basedatos import BaseDatos
from bitcoinai.seguridad.tokens import generar_token, hash_token

MINUTO = 60_000
DURACION_CODIGO = 15 * MINUTO
INTENTOS_CODIGO = 5
ESPERA_REENVIO = MINUTO  # entre un correo y el siguiente


def generar_codigo() -> str:
    """Seis dígitos al azar con ``secrets`` (no ``random``, que se puede adivinar)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_codigo(usuario_id: int, codigo: str) -> bytes:
    # Con el id adentro, el mismo código en dos cuentas no deja el mismo hash.
    return hash_token(f"{usuario_id}:{codigo}")


@dataclass(frozen=True, slots=True)
class Pendiente:
    usuario_id: int
    codigo_hash: bytes
    expira_en: int
    intentos: int
    enviado_en: int


class RepositorioVerificaciones:
    def __init__(self, bd: BaseDatos, reloj: Callable[[], int] = lambda: int(time.time() * 1000)) -> None:
        self._bd = bd
        self._reloj = reloj

    def nueva(self, usuario_id: int, codigo: str | None) -> str:
        """Token nuevo para la cuenta. Con ``codigo`` también lo reemplaza (y su vencimiento);
        sin él, conserva el código que ya se envió. Devuelve el token."""
        token = generar_token()
        ahora = self._reloj()
        actual = self.de_usuario(usuario_id)
        if codigo is None and actual is not None:
            self._bd.ejecutar("UPDATE verificaciones_correo SET token_hash = ? WHERE usuario_id = ?",
                              (hash_token(token), usuario_id))
            return token
        if codigo is None:
            raise ValueError("No hay código enviado para conservar")
        self._bd.ejecutar(
            "INSERT OR REPLACE INTO verificaciones_correo"
            " (usuario_id, token_hash, codigo_hash, expira_en, intentos, enviado_en) VALUES (?, ?, ?, ?, 0, ?)",
            (usuario_id, hash_token(token), hash_codigo(usuario_id, codigo), ahora + DURACION_CODIGO, ahora))
        return token

    def reemplazar_codigo(self, usuario_id: int, codigo: str) -> None:
        """Otro código para la misma verificación (el token sigue igual): vuelve a 15 min y 5 intentos."""
        ahora = self._reloj()
        self._bd.ejecutar(
            "UPDATE verificaciones_correo SET codigo_hash = ?, expira_en = ?, intentos = 0, enviado_en = ?"
            " WHERE usuario_id = ?", (hash_codigo(usuario_id, codigo), ahora + DURACION_CODIGO, ahora, usuario_id))

    def de_usuario(self, usuario_id: int) -> Pendiente | None:
        fila = self._bd.una("SELECT * FROM verificaciones_correo WHERE usuario_id = ?", (usuario_id,))
        return None if fila is None else Pendiente(fila["usuario_id"], fila["codigo_hash"], fila["expira_en"],
                                                   fila["intentos"], fila["enviado_en"])

    def usuario_del_token(self, token: str) -> int | None:
        if not token:
            return None
        fila = self._bd.una("SELECT usuario_id FROM verificaciones_correo WHERE token_hash = ?", (hash_token(token),))
        return None if fila is None else int(fila["usuario_id"])

    def comprobar(self, usuario_id: int, codigo: str) -> bool:
        """Si el código es el vigente. Un fallo gasta un intento; con 5 fallos o vencido, ya no sirve."""
        p = self.de_usuario(usuario_id)
        if p is None or p.expira_en <= self._reloj() or p.intentos >= INTENTOS_CODIGO:
            return False
        if secrets.compare_digest(p.codigo_hash, hash_codigo(usuario_id, codigo)):
            return True
        self._bd.ejecutar("UPDATE verificaciones_correo SET intentos = intentos + 1 WHERE usuario_id = ?",
                          (usuario_id,))
        return False

    def espera_reenvio(self, usuario_id: int) -> int:
        """Milisegundos que faltan para poder enviar otro código (0 si ya se puede)."""
        p = self.de_usuario(usuario_id)
        return 0 if p is None else max(0, p.enviado_en + ESPERA_REENVIO - self._reloj())

    def borrar(self, usuario_id: int) -> None:
        self._bd.ejecutar("DELETE FROM verificaciones_correo WHERE usuario_id = ?", (usuario_id,))
