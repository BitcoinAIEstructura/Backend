"""Reglas de las cuentas: registro, inicio de sesión, verificación en dos pasos y sesiones.

No sabe nada de HTTP: recibe datos y la IP/navegador de quien pide, y devuelve
resultados o lanza errores del dominio que la API traduce a códigos HTTP.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from bitcoinai.basedatos import BaseDatos
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.seguridad.contrasenas import HashContrasenas
from bitcoinai.seguridad.limitador import LimitadorIntentos
from bitcoinai.usuarios.actividad import RegistroActividad, TipoActividad
from bitcoinai.usuarios.modelo import DatosRegistro, Usuario
from bitcoinai.usuarios.repositorio import RepositorioUsuarios, UsuarioDuplicadoError
from bitcoinai.usuarios.sesiones import RepositorioSesiones


class CuentaError(Exception):
    """Error de las cuentas con un mensaje que se puede mostrar al usuario."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class RegistroRechazadoError(CuentaError):
    """El correo o el documento ya tienen cuenta."""


class DemasiadosIntentosError(CuentaError):
    """Se superó el límite de intentos; ``espera`` dice cuántos segundos faltan."""

    def __init__(self, espera: float) -> None:
        minutos = max(1, round(espera / 60))
        super().__init__(f"Demasiados intentos. Vuelve a intentarlo en {minutos} "
                         f"minuto{'s' if minutos != 1 else ''}.")
        self.espera = espera


@dataclass(frozen=True, slots=True)
class Cliente:
    """Quién hace la petición: su IP y su navegador (para la actividad y los límites)."""

    ip: str
    agente: str


class ServicioCuentas:
    """Punto de entrada de todo lo relacionado con cuentas."""

    def __init__(self, bd: BaseDatos, cifrador: Cifrador, hasher: HashContrasenas,
                 reloj_ms: Callable[[], int] = lambda: int(time.time() * 1000),
                 reloj_s: Callable[[], float] = time.time,
                 limite_registro: LimitadorIntentos | None = None) -> None:
        self.usuarios = RepositorioUsuarios(bd, cifrador, reloj_ms)
        self.sesiones = RepositorioSesiones(bd, reloj_ms)
        self.actividad = RegistroActividad(bd, reloj_ms)
        self._hasher = hasher
        self._reloj_s = reloj_s
        # 10 cuentas por hora desde una misma IP: frena la creación masiva de cuentas.
        self._limite_registro = limite_registro or LimitadorIntentos(10, 3600)

    # ---------- registro ----------

    def registrar(self, datos: DatosRegistro, cliente: Cliente) -> tuple[Usuario, str]:
        """Crea la cuenta y abre su primera sesión.

        Returns:
            El usuario y el token de sesión.

        Raises:
            DemasiadosIntentosError: si esa IP creó demasiadas cuentas hace poco.
            RegistroRechazadoError: si el correo o el documento ya están registrados.
        """
        clave = f"registro:{cliente.ip}"
        espera = self._limite_registro.espera(clave)
        if espera > 0:
            raise DemasiadosIntentosError(espera)
        self._limite_registro.registrar(clave)
        try:
            usuario = self.usuarios.crear(datos, self._hasher.calcular(datos.contrasena))
        except UsuarioDuplicadoError:
            raise RegistroRechazadoError("Ya existe una cuenta con ese correo o con ese documento") from None
        self.actividad.registrar(usuario.id, TipoActividad.REGISTRO, cliente.ip)
        token, _ = self.sesiones.crear(usuario.id, cliente.ip, cliente.agente)
        self.actividad.registrar(usuario.id, TipoActividad.INICIO_SESION, cliente.ip, cliente.agente)
        return usuario, token
