"""Acceso a la tabla de usuarios y a sus códigos de respaldo.

Aquí se cifra al guardar y se descifra al leer: el resto del código trabaja con
datos en claro y nunca arma SQL.
"""

import sqlite3
import time
from collections.abc import Callable

from bitcoinai.basedatos import BaseDatos, Fila
from bitcoinai.estructuras import Lista
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.usuarios.modelo import Credenciales, DatosRegistro, Usuario
from bitcoinai.usuarios.validacion import TipoDocumento

CORREO = "usuarios.correo"
DOCUMENTO = "usuarios.documento"
TELEFONO = "usuarios.telefono"
TOTP = "usuarios.totp"


class UsuarioDuplicadoError(Exception):
    """Ya hay una cuenta con ese correo o con ese documento."""


def _ahora_ms() -> int:
    return int(time.time() * 1000)


class RepositorioUsuarios:
    """Usuarios guardados con sus datos personales cifrados."""

    def __init__(self, bd: BaseDatos, cifrador: Cifrador, reloj: Callable[[], int] = _ahora_ms) -> None:
        self._bd = bd
        self._cifrador = cifrador
        self._reloj = reloj

    # ---------- índices ciegos ----------

    def _indice_correo(self, correo: str) -> bytes:
        return self._cifrador.indice(correo, CORREO)

    def _indice_documento(self, tipo: TipoDocumento, numero: str) -> bytes:
        return self._cifrador.indice(f"{tipo.name}:{numero}", DOCUMENTO)

    # ---------- crear y leer ----------

    def crear(self, datos: DatosRegistro, contrasena_hash: str) -> Usuario:
        """Guarda una cuenta nueva.

        Raises:
            UsuarioDuplicadoError: si el correo o el documento ya están registrados.
        """
        c = self._cifrador
        ahora = self._reloj()
        try:
            nuevo_id = self._bd.ejecutar(
                "INSERT INTO usuarios (nombre, apellido, correo_indice, correo_cifrado, tipo_documento,"
                " documento_indice, documento_cifrado, telefono_cifrado, contrasena_hash, creado_en, actualizado_en)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (datos.nombre, datos.apellido, self._indice_correo(datos.correo), c.cifrar(datos.correo, CORREO),
                 datos.tipo_documento.name, self._indice_documento(datos.tipo_documento, datos.numero_documento),
                 c.cifrar(datos.numero_documento, DOCUMENTO), c.cifrar(datos.telefono, TELEFONO), contrasena_hash,
                 ahora, ahora))
        except sqlite3.IntegrityError as error:
            raise UsuarioDuplicadoError("Ya existe una cuenta con ese correo o documento") from error
        usuario = self.por_id(nuevo_id)
        assert usuario is not None
        return usuario

    def _usuario(self, fila: Fila) -> Usuario:
        c = self._cifrador
        return Usuario(
            id=fila["id"], nombre=fila["nombre"], apellido=fila["apellido"],
            correo=c.descifrar(fila["correo_cifrado"], CORREO),
            tipo_documento=TipoDocumento[fila["tipo_documento"]],
            numero_documento=c.descifrar(fila["documento_cifrado"], DOCUMENTO),
            telefono=c.descifrar(fila["telefono_cifrado"], TELEFONO),
            verificacion_dos_pasos=bool(fila["totp_activo"]), creado_en=fila["creado_en"])

    def por_id(self, usuario_id: int) -> Usuario | None:
        fila = self._bd.una("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        return None if fila is None else self._usuario(fila)

    def existe_documento(self, tipo: TipoDocumento, numero: str) -> bool:
        return self._bd.una("SELECT 1 FROM usuarios WHERE documento_indice = ?",
                            (self._indice_documento(tipo, numero),)) is not None

    def credenciales_por_correo(self, correo: str) -> Credenciales | None:
        fila = self._bd.una("SELECT * FROM usuarios WHERE correo_indice = ?", (self._indice_correo(correo),))
        return None if fila is None else self._credenciales(fila)

    def credenciales(self, usuario_id: int) -> Credenciales | None:
        fila = self._bd.una("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        return None if fila is None else self._credenciales(fila)

    def _credenciales(self, fila: Fila) -> Credenciales:
        secreto = fila["totp_secreto_cifrado"]
        return Credenciales(fila["id"], fila["contrasena_hash"],
                            None if secreto is None else self._cifrador.descifrar(secreto, TOTP),
                            bool(fila["totp_activo"]), fila["totp_ultimo_paso"])

    # ---------- cambios ----------

    def cambiar_contrasena(self, usuario_id: int, contrasena_hash: str) -> None:
        self._bd.ejecutar("UPDATE usuarios SET contrasena_hash = ?, actualizado_en = ? WHERE id = ?",
                          (contrasena_hash, self._reloj(), usuario_id))

    def guardar_totp(self, usuario_id: int, secreto: str | None, activo: bool) -> None:
        """Guarda (cifrado) o borra el secreto de la verificación en dos pasos."""
        cifrado = None if secreto is None else self._cifrador.cifrar(secreto, TOTP)
        self._bd.ejecutar(
            "UPDATE usuarios SET totp_secreto_cifrado = ?, totp_activo = ?, totp_ultimo_paso = NULL,"
            " actualizado_en = ? WHERE id = ?", (cifrado, int(activo), self._reloj(), usuario_id))

    def marcar_paso_totp(self, usuario_id: int, paso: int) -> bool:
        """Anota el último código usado. False si otro ya usó ese paso (evita reutilizarlo a la vez)."""
        return self._bd.contar_cambios(
            "UPDATE usuarios SET totp_ultimo_paso = ? WHERE id = ?"
            " AND (totp_ultimo_paso IS NULL OR totp_ultimo_paso < ?)", (paso, usuario_id, paso)) == 1

    # ---------- códigos de respaldo ----------

    def reemplazar_codigos(self, usuario_id: int, hashes: Lista[bytes]) -> None:
        with self._bd.transaccion():
            self._bd.ejecutar("DELETE FROM codigos_respaldo WHERE usuario_id = ?", (usuario_id,))
            for codigo_hash in hashes:
                self._bd.ejecutar("INSERT INTO codigos_respaldo (usuario_id, codigo_hash) VALUES (?, ?)",
                                  (usuario_id, codigo_hash))

    def usar_codigo(self, usuario_id: int, codigo_hash: bytes) -> bool:
        """Marca un código como usado. False si no existe o ya se había usado."""
        return self._bd.contar_cambios(
            "UPDATE codigos_respaldo SET usado_en = ? WHERE usuario_id = ? AND codigo_hash = ? AND usado_en IS NULL",
            (self._reloj(), usuario_id, codigo_hash)) == 1

    def codigos_restantes(self, usuario_id: int) -> int:
        fila = self._bd.una("SELECT COUNT(*) FROM codigos_respaldo WHERE usuario_id = ? AND usado_en IS NULL",
                            (usuario_id,))
        return 0 if fila is None else int(fila[0])
