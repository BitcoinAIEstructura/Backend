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
from bitcoinai.usuarios.validacion import DatoInvalidoError, normalizar_correo

FALLOS_POR_CORREO = 5
FALLOS_POR_IP = 20
VENTANA_FALLOS = 15 * 60


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


class CredencialesInvalidasError(CuentaError):
    """Correo o contraseña equivocados (nunca se dice cuál de los dos)."""

    def __init__(self) -> None:
        super().__init__("Correo o contraseña incorrectos")


@dataclass(frozen=True, slots=True)
class ResultadoInicio:
    """Resultado de un inicio de sesión con la contraseña correcta.

    - Sin verificación en dos pasos: ``usuario`` y ``token_sesion``.
    - Con verificación en dos pasos: solo ``token_desafio``; falta el código de 6 dígitos.
    """

    usuario: Usuario | None = None
    token_sesion: str | None = None
    token_desafio: str | None = None


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
        # Contraseñas equivocadas: 5 por correo y 20 por IP cada 15 minutos.
        self._fallos_correo = LimitadorIntentos(FALLOS_POR_CORREO, VENTANA_FALLOS, reloj_s)
        self._fallos_ip = LimitadorIntentos(FALLOS_POR_IP, VENTANA_FALLOS, reloj_s)

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

    # ---------- inicio de sesión ----------

    def _comprobar_limites(self, clave_correo: str, cliente: Cliente) -> None:
        espera = max(self._fallos_correo.espera(clave_correo), self._fallos_ip.espera(f"ip:{cliente.ip}"))
        if espera > 0:
            raise DemasiadosIntentosError(espera)

    def _anotar_fallo(self, clave_correo: str, cliente: Cliente) -> None:
        self._fallos_correo.registrar(clave_correo)
        self._fallos_ip.registrar(f"ip:{cliente.ip}")

    def iniciar_sesion(self, correo: str, contrasena: str, cliente: Cliente) -> ResultadoInicio:
        """Comprueba correo y contraseña.

        Mismo mensaje y mismo tiempo de respuesta exista o no el correo, para no
        revelar quién tiene cuenta. Tras 5 fallos para un correo (o 20 desde una IP)
        en 15 minutos, se bloquea hasta que pase la ventana, exista o no la cuenta.

        Raises:
            DemasiadosIntentosError: si está bloqueado.
            CredencialesInvalidasError: si el correo o la contraseña no coinciden.
        """
        try:
            correo = normalizar_correo(correo)
        except DatoInvalidoError:
            raise CredencialesInvalidasError() from None
        clave = f"correo:{correo}"
        self._comprobar_limites(clave, cliente)
        credenciales = self.usuarios.credenciales_por_correo(correo)
        if credenciales is None:
            self._hasher.verificar_senuelo(contrasena)
            self._anotar_fallo(clave, cliente)
            raise CredencialesInvalidasError()
        if not self._hasher.verificar(credenciales.contrasena_hash, contrasena):
            self._anotar_fallo(clave, cliente)
            self.actividad.registrar(credenciales.usuario_id, TipoActividad.INICIO_FALLIDO, cliente.ip,
                                     cliente.agente)
            raise CredencialesInvalidasError()
        self._fallos_correo.reiniciar(clave)
        if self._hasher.necesita_actualizarse(credenciales.contrasena_hash):
            self.usuarios.cambiar_contrasena(credenciales.usuario_id, self._hasher.calcular(contrasena))
        if credenciales.totp_activo:
            return ResultadoInicio(token_desafio=self.sesiones.crear_desafio(credenciales.usuario_id))
        usuario, token = self._abrir_sesion(credenciales.usuario_id, cliente)
        return ResultadoInicio(usuario=usuario, token_sesion=token)

    def _abrir_sesion(self, usuario_id: int, cliente: Cliente, detalle: str = "") -> tuple[Usuario, str]:
        usuario = self.usuarios.por_id(usuario_id)
        assert usuario is not None
        token, _ = self.sesiones.crear(usuario_id, cliente.ip, cliente.agente)
        self.actividad.registrar(usuario_id, TipoActividad.INICIO_SESION, cliente.ip,
                                 f"{cliente.agente} {detalle}".strip())
        return usuario, token
