"""Datos de una cuenta de usuario."""

from dataclasses import dataclass

from bitcoinai.seguridad.politica import problemas_contrasena
from bitcoinai.usuarios.validacion import (
    DatoInvalidoError,
    TipoDocumento,
    leer_tipo_documento,
    normalizar_correo,
    normalizar_documento,
    normalizar_nombre,
    normalizar_telefono,
)


def enmascarar(texto: str, visibles: int = 4) -> str:
    """Oculta todo menos los últimos caracteres: "1023456789" → "******6789"."""
    if len(texto) <= visibles:
        return "*" * len(texto)
    return "*" * (len(texto) - visibles) + texto[-visibles:]


@dataclass(frozen=True, slots=True)
class DatosRegistro:
    """Lo que pide el formulario de registro, ya validado y normalizado.

    Se construye con ``DatosRegistro.validar(...)``, que lanza ``DatoInvalidoError``
    con el primer problema encontrado.
    """

    nombre: str
    apellido: str
    correo: str
    tipo_documento: TipoDocumento
    numero_documento: str
    telefono: str
    contrasena: str

    @classmethod
    def validar(cls, nombre: str, apellido: str, correo: str, tipo_documento: str, numero_documento: str,
                telefono: str, contrasena: str) -> "DatosRegistro":
        tipo = leer_tipo_documento(tipo_documento)
        datos = cls(
            nombre=normalizar_nombre(nombre, "nombre"),
            apellido=normalizar_nombre(apellido, "apellido"),
            correo=normalizar_correo(correo),
            tipo_documento=tipo,
            numero_documento=normalizar_documento(tipo, numero_documento),
            telefono=normalizar_telefono(telefono),
            contrasena=contrasena,
        )
        problemas = problemas_contrasena(contrasena, (datos.nombre, datos.apellido, datos.correo,
                                                      datos.numero_documento))
        if not problemas.esta_vacia():
            raise DatoInvalidoError("contrasena", problemas.primero())
        return datos


@dataclass(frozen=True, slots=True)
class Usuario:
    """Una cuenta, con los datos personales ya descifrados (nunca incluye la contraseña)."""

    id: int
    nombre: str
    apellido: str
    correo: str
    tipo_documento: TipoDocumento
    numero_documento: str
    telefono: str
    verificacion_dos_pasos: bool
    creado_en: int

    @property
    def documento_enmascarado(self) -> str:
        return enmascarar(self.numero_documento)

    @property
    def telefono_enmascarado(self) -> str:
        return self.telefono[:3] + enmascarar(self.telefono[3:])


@dataclass(frozen=True, slots=True)
class Credenciales:
    """Lo necesario para comprobar un inicio de sesión (uso interno, nunca sale por la API)."""

    usuario_id: int
    contrasena_hash: str
    totp_secreto: str | None
    totp_activo: bool
    totp_ultimo_paso: int | None
