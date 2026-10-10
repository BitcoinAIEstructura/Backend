"""Migraciones: los pasos que crean y actualizan las tablas, en orden.

Cada migración tiene un número de versión. La base guarda la última aplicada en
``PRAGMA user_version``; al arrancar se aplican solo las que faltan, cada una en
una transacción (si una falla, no queda a medias). Nunca se modifica una
migración ya publicada: los cambios van en una nueva al final.
"""

import logging
from dataclasses import dataclass

from bitcoinai.basedatos.conexion import BaseDatos

LOG = logging.getLogger("bitcoinai.basedatos")


@dataclass(frozen=True, slots=True)
class Migracion:
    version: int
    descripcion: str
    instrucciones: tuple[str, ...]


MIGRACIONES: tuple[Migracion, ...] = (
    Migracion(1, "usuarios, sesiones, verificación en dos pasos y actividad", (
        # Los datos personales van cifrados (``*_cifrado``). Para buscar por correo o
        # documento sin descifrar, se guarda además un "índice ciego" (HMAC) único.
        """CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            apellido TEXT NOT NULL,
            correo_indice BLOB NOT NULL UNIQUE,
            correo_cifrado BLOB NOT NULL,
            tipo_documento TEXT NOT NULL CHECK (tipo_documento IN ('CC', 'CE')),
            documento_indice BLOB NOT NULL UNIQUE,
            documento_cifrado BLOB NOT NULL,
            telefono_cifrado BLOB NOT NULL,
            contrasena_hash TEXT NOT NULL,
            totp_secreto_cifrado BLOB,
            totp_activo INTEGER NOT NULL DEFAULT 0,
            totp_ultimo_paso INTEGER,
            creado_en INTEGER NOT NULL,
            actualizado_en INTEGER NOT NULL
        )""",
        """CREATE TABLE codigos_respaldo (
            id INTEGER PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            codigo_hash BLOB NOT NULL,
            usado_en INTEGER
        )""",
        "CREATE INDEX codigos_respaldo_usuario ON codigos_respaldo(usuario_id)",
        # De la sesión solo se guarda el hash del token: quien lea la base no puede usarlo.
        """CREATE TABLE sesiones (
            id INTEGER PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            token_hash BLOB NOT NULL UNIQUE,
            creada_en INTEGER NOT NULL,
            expira_en INTEGER NOT NULL,
            ultima_actividad INTEGER NOT NULL,
            ip TEXT NOT NULL,
            agente TEXT NOT NULL,
            cerrada_en INTEGER
        )""",
        "CREATE INDEX sesiones_usuario ON sesiones(usuario_id)",
        # Inicio de sesión a medias: contraseña correcta, falta el código de 6 dígitos.
        """CREATE TABLE desafios (
            token_hash BLOB PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            expira_en INTEGER NOT NULL,
            intentos INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE actividad (
            id INTEGER PRIMARY KEY,
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            momento INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            ip TEXT NOT NULL,
            detalle TEXT NOT NULL
        )""",
        "CREATE INDEX actividad_usuario ON actividad(usuario_id, momento)",
    )),
)


def version_actual(bd: BaseDatos) -> int:
    fila = bd.una("PRAGMA user_version")
    return int(fila[0]) if fila is not None else 0


def migrar(bd: BaseDatos, migraciones: tuple[Migracion, ...] = MIGRACIONES) -> int:
    """Aplica las migraciones pendientes, en orden.

    Returns:
        Cuántas se aplicaron.

    Raises:
        RuntimeError: si la base es de una versión más nueva que este código.
    """
    actual = version_actual(bd)
    ultima = migraciones[-1].version if migraciones else 0
    if actual > ultima:
        raise RuntimeError(f"La base de datos es de la versión {actual} y este código solo conoce hasta la {ultima}")
    aplicadas = 0
    for migracion in migraciones:
        if migracion.version <= actual:
            continue
        with bd.transaccion():
            for instruccion in migracion.instrucciones:
                bd.ejecutar(instruccion)
            # user_version no admite parámetros; el número sale del código, no del usuario.
            bd.ejecutar(f"PRAGMA user_version = {int(migracion.version)}")
        LOG.info("Migración %d aplicada: %s", migracion.version, migracion.descripcion)
        aplicadas += 1
    return aplicadas
