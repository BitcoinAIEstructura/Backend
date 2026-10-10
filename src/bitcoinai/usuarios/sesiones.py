"""Sesiones abiertas y desafíos de la verificación en dos pasos.

- **Sesión:** dura como máximo ``DURACION_SESION`` y se cierra sola tras
  ``INACTIVIDAD_MAXIMA`` sin usarse. Cada uso renueva la actividad.
- **Desafío:** cuando la contraseña es correcta pero falta el código de 6
  dígitos, se entrega un token de desafío que vale ``DURACION_DESAFIO`` y admite
  ``INTENTOS_DESAFIO`` códigos equivocados.

De ambos solo se guarda el hash del token.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from bitcoinai.basedatos import BaseDatos, Fila
from bitcoinai.estructuras import Lista
from bitcoinai.seguridad.tokens import generar_token, hash_token

MINUTO = 60_000
DURACION_SESION = 12 * 60 * MINUTO
INACTIVIDAD_MAXIMA = 2 * 60 * MINUTO
DURACION_DESAFIO = 5 * MINUTO
INTENTOS_DESAFIO = 5
LARGO_AGENTE = 200


@dataclass(frozen=True, slots=True)
class Sesion:
    id: int
    usuario_id: int
    creada_en: int
    expira_en: int
    ultima_actividad: int
    ip: str
    agente: str


def _ahora_ms() -> int:
    return int(time.time() * 1000)


def _sesion(fila: Fila) -> Sesion:
    return Sesion(fila["id"], fila["usuario_id"], fila["creada_en"], fila["expira_en"], fila["ultima_actividad"],
                  fila["ip"], fila["agente"])


class RepositorioSesiones:
    def __init__(self, bd: BaseDatos, reloj: Callable[[], int] = _ahora_ms) -> None:
        self._bd = bd
        self._reloj = reloj

    # ---------- sesiones ----------

    def crear(self, usuario_id: int, ip: str, agente: str) -> tuple[str, Sesion]:
        """Abre una sesión. Returns: el token (para la cookie; no se guarda) y la sesión."""
        token = generar_token()
        ahora = self._reloj()
        sesion_id = self._bd.ejecutar(
            "INSERT INTO sesiones (usuario_id, token_hash, creada_en, expira_en, ultima_actividad, ip, agente)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (usuario_id, hash_token(token), ahora, ahora + DURACION_SESION, ahora, ip, agente[:LARGO_AGENTE]))
        return token, Sesion(sesion_id, usuario_id, ahora, ahora + DURACION_SESION, ahora, ip, agente[:LARGO_AGENTE])

    def validar(self, token: str) -> Sesion | None:
        """La sesión del token si sigue vigente (y renueva su actividad); si no, None."""
        ahora = self._reloj()
        fila = self._bd.una(
            "SELECT * FROM sesiones WHERE token_hash = ? AND cerrada_en IS NULL AND expira_en > ?"
            " AND ultima_actividad > ?", (hash_token(token), ahora, ahora - INACTIVIDAD_MAXIMA))
        if fila is None:
            return None
        self._bd.ejecutar("UPDATE sesiones SET ultima_actividad = ? WHERE id = ?", (ahora, fila["id"]))
        sesion = _sesion(fila)
        return Sesion(sesion.id, sesion.usuario_id, sesion.creada_en, sesion.expira_en, ahora, sesion.ip,
                      sesion.agente)

    def activas(self, usuario_id: int) -> Lista[Sesion]:
        """Sesiones abiertas de un usuario, la más reciente primero."""
        ahora = self._reloj()
        filas = self._bd.todas(
            "SELECT * FROM sesiones WHERE usuario_id = ? AND cerrada_en IS NULL AND expira_en > ?"
            " AND ultima_actividad > ? ORDER BY ultima_actividad DESC",
            (usuario_id, ahora, ahora - INACTIVIDAD_MAXIMA))
        resultado: Lista[Sesion] = Lista()
        for fila in filas:
            resultado.agregar(_sesion(fila))
        return resultado

    def cerrar_token(self, token: str) -> bool:
        return self._bd.contar_cambios("UPDATE sesiones SET cerrada_en = ? WHERE token_hash = ? AND cerrada_en IS NULL",
                                       (self._reloj(), hash_token(token))) == 1

    def cerrar(self, usuario_id: int, sesion_id: int) -> bool:
        """Cierra una sesión del usuario (no de otro). False si no era suya o ya estaba cerrada."""
        return self._bd.contar_cambios(
            "UPDATE sesiones SET cerrada_en = ? WHERE id = ? AND usuario_id = ? AND cerrada_en IS NULL",
            (self._reloj(), sesion_id, usuario_id)) == 1

    def cerrar_todas(self, usuario_id: int, excepto: int | None = None) -> int:
        """Cierra todas las sesiones del usuario menos ``excepto``. Returns: cuántas cerró."""
        return self._bd.contar_cambios(
            "UPDATE sesiones SET cerrada_en = ? WHERE usuario_id = ? AND cerrada_en IS NULL AND id != ?",
            (self._reloj(), usuario_id, -1 if excepto is None else excepto))

    # ---------- desafíos de la verificación en dos pasos ----------

    def crear_desafio(self, usuario_id: int) -> str:
        token = generar_token()
        self._bd.ejecutar("INSERT INTO desafios (token_hash, usuario_id, expira_en) VALUES (?, ?, ?)",
                          (hash_token(token), usuario_id, self._reloj() + DURACION_DESAFIO))
        return token

    def usuario_del_desafio(self, token: str) -> int | None:
        fila = self._bd.una("SELECT usuario_id FROM desafios WHERE token_hash = ? AND expira_en > ? AND intentos < ?",
                            (hash_token(token), self._reloj(), INTENTOS_DESAFIO))
        return None if fila is None else int(fila["usuario_id"])

    def fallo_en_desafio(self, token: str) -> None:
        self._bd.ejecutar("UPDATE desafios SET intentos = intentos + 1 WHERE token_hash = ?", (hash_token(token),))

    def borrar_desafio(self, token: str) -> None:
        self._bd.ejecutar("DELETE FROM desafios WHERE token_hash = ?", (hash_token(token),))

    def limpiar_vencidos(self) -> None:
        """Borra desafíos vencidos y sesiones cerradas o vencidas hace más de 30 días."""
        ahora = self._reloj()
        self._bd.ejecutar("DELETE FROM desafios WHERE expira_en <= ?", (ahora,))
        self._bd.ejecutar("DELETE FROM sesiones WHERE expira_en <= ?", (ahora - 30 * 24 * 60 * MINUTO,))
