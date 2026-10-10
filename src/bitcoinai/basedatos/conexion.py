"""Conexión a la base de datos SQLite, segura para varios hilos."""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from bitcoinai.estructuras import Lista

Parametros = tuple[Any, ...] | dict[str, Any]
"""Parámetros de una consulta: posicionales (``?``) o con nombre (``:nombre``)."""

Fila = sqlite3.Row
"""Una fila del resultado; se lee por nombre de columna: ``fila["correo"]``."""


class BaseDatos:
    """Base de datos SQLite de la aplicación (usuarios, sesiones y actividad).

    - Una sola conexión protegida por un candado: FastAPI atiende peticiones en
      varios hilos y así nunca se pisan.
    - Modo WAL (lecturas sin bloquear escrituras) y claves foráneas activadas.
    - Las consultas siempre van con parámetros (``?``), nunca armando el texto
      del SQL con datos del usuario: eso evita la inyección de SQL.

    Con ``":memory:"`` se crea en memoria (para pruebas).
    """

    def __init__(self, ruta: str | Path) -> None:
        if str(ruta) != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.ruta = str(ruta)
        self._conexion = sqlite3.connect(self.ruta, check_same_thread=False, isolation_level=None)
        self._conexion.row_factory = sqlite3.Row
        self._candado = threading.RLock()
        with self._candado:
            self._conexion.execute("PRAGMA foreign_keys = ON")
            self._conexion.execute("PRAGMA busy_timeout = 5000")
            if self.ruta != ":memory:":
                self._conexion.execute("PRAGMA journal_mode = WAL")

    def ejecutar(self, sql: str, parametros: Parametros = ()) -> int:
        """Ejecuta una instrucción (INSERT, UPDATE, DELETE…).

        Returns:
            El id de la última fila insertada (útil tras un INSERT).
        """
        with self._candado:
            cursor = self._conexion.execute(sql, parametros)
            return cursor.lastrowid or 0

    def contar_cambios(self, sql: str, parametros: Parametros = ()) -> int:
        """Ejecuta un UPDATE o DELETE y devuelve cuántas filas cambió."""
        with self._candado:
            return self._conexion.execute(sql, parametros).rowcount

    def una(self, sql: str, parametros: Parametros = ()) -> Fila | None:
        """Primera fila del resultado, o None si no hay."""
        with self._candado:
            fila: Fila | None = self._conexion.execute(sql, parametros).fetchone()
            return fila

    def todas(self, sql: str, parametros: Parametros = ()) -> Lista[Fila]:
        """Todas las filas del resultado, en orden, en una ``Lista``. Complejidad: O(n)."""
        resultado: Lista[Fila] = Lista()
        with self._candado:
            for fila in self._conexion.execute(sql, parametros):
                resultado.agregar(fila)
        return resultado

    @contextmanager
    def transaccion(self) -> Iterator["BaseDatos"]:
        """Agrupa varias instrucciones: o se aplican todas o ninguna.

        Mientras dura, ningún otro hilo usa la conexión.
        """
        with self._candado:
            self._conexion.execute("BEGIN IMMEDIATE")
            try:
                yield self
            except BaseException:
                self._conexion.execute("ROLLBACK")
                raise
            self._conexion.execute("COMMIT")

    def cerrar(self) -> None:
        with self._candado:
            self._conexion.close()
