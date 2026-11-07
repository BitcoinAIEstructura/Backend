"""Reglas de las cuentas: registro, inicio de sesión, verificación en dos pasos y sesiones.

No sabe nada de HTTP: recibe datos y la IP/navegador de quien pide, y devuelve
resultados o lanza errores del dominio que la API traduce a códigos HTTP.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from bitcoinai.basedatos import BaseDatos
from bitcoinai.estructuras import Lista
from bitcoinai.notificaciones import EnviadorCorreo
from bitcoinai.notificaciones.plantillas import codigo_verificacion
from bitcoinai.seguridad import totp
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.seguridad.contrasenas import HashContrasenas
from bitcoinai.seguridad.limitador import LimitadorIntentos
from bitcoinai.seguridad.politica import problemas_contrasena
from bitcoinai.seguridad.respaldo import generar_codigos, hash_codigo
from bitcoinai.usuarios.actividad import EventoActividad, RegistroActividad, TipoActividad
from bitcoinai.usuarios.modelo import Credenciales, DatosRegistro, Usuario
from bitcoinai.usuarios.repositorio import RepositorioUsuarios, UsuarioDuplicadoError
from bitcoinai.usuarios.sesiones import RepositorioSesiones, Sesion
from bitcoinai.usuarios.validacion import DatoInvalidoError, normalizar_correo
from bitcoinai.usuarios.verificacion import (
    DURACION_CODIGO,
    INTENTOS_CODIGO,
    MINUTO,
    RepositorioVerificaciones,
    generar_codigo,
)

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


class CodigoInvalidoError(CuentaError):
    def __init__(self) -> None:
        super().__init__("El código no es válido o ya se usó")


class DesafioVencidoError(CuentaError):
    def __init__(self) -> None:
        super().__init__("El inicio de sesión venció o tuvo demasiados intentos; vuelve a escribir tu contraseña")


class SesionInvalidaError(CuentaError):
    def __init__(self) -> None:
        super().__init__("Tu sesión terminó; vuelve a iniciar sesión")


class VerificacionVencidaError(CuentaError):
    def __init__(self) -> None:
        super().__init__("El código venció o tuvo demasiados intentos; pide uno nuevo")


class EsperaReenvioError(CuentaError):
    """Se pidió otro código demasiado pronto; ``espera`` en segundos."""

    def __init__(self, espera: float) -> None:
        segundos = max(1, round(espera))
        super().__init__(f"Espera {segundos} s para pedir otro código")
        self.espera = espera


class OperacionCuentaError(CuentaError):
    """La operación no tiene sentido en el estado actual de la cuenta (por ejemplo, activar 2FA dos veces)."""


@dataclass(frozen=True, slots=True)
class ConfiguracionDosPasos:
    """Lo que se muestra al activar la verificación: el secreto y el enlace para el código QR."""

    secreto: str
    uri: str


@dataclass(frozen=True, slots=True)
class ResultadoInicio:
    """Resultado de un inicio de sesión con la contraseña correcta.

    - Sin verificación en dos pasos: ``usuario`` y ``token_sesion``.
    - Con verificación en dos pasos: solo ``token_desafio``; falta el código de 6 dígitos.
    - Si aún no confirmó el correo: ``token_verificacion`` y ``correo`` (enmascarado); falta
      el código que llegó (o que se acaba de reenviar) al correo.
    """

    usuario: Usuario | None = None
    token_sesion: str | None = None
    token_desafio: str | None = None
    token_verificacion: str | None = None
    correo: str | None = None


@dataclass(frozen=True, slots=True)
class ResultadoRegistro:
    """Cuenta creada. Con correo por confirmar: ``token_verificacion`` (sin sesión todavía);
    si no se exige confirmar (sin enviador de correo, como en las pruebas): ``token_sesion``."""

    usuario: Usuario
    token_sesion: str | None = None
    token_verificacion: str | None = None

    @property
    def correo(self) -> str:
        return correo_enmascarado(self.usuario.correo)

    def sesion(self) -> tuple[Usuario, str]:
        """El usuario y su sesión, cuando la cuenta quedó abierta al crearla."""
        assert self.token_sesion is not None, "la cuenta espera confirmar el correo"
        return self.usuario, self.token_sesion


def correo_enmascarado(correo: str) -> str:
    """De "valentina@prueba.co" deja "va*******@prueba.co": se reconoce sin mostrarlo entero."""
    nombre, _, dominio = correo.partition("@")
    visibles = min(2, max(1, len(nombre) // 3))
    return f"{nombre[:visibles]}{'*' * max(3, len(nombre) - visibles)}@{dominio}"


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
                 limite_registro: LimitadorIntentos | None = None,
                 correo: EnviadorCorreo | None = None) -> None:
        """Con ``correo``, las cuentas nuevas confirman su correo con un código antes de entrar.
        Sin él (las pruebas que no tratan del correo), la cuenta queda abierta al crearla."""
        self.usuarios = RepositorioUsuarios(bd, cifrador, reloj_ms)
        self.verificaciones = RepositorioVerificaciones(bd, reloj_ms)
        self._correo = correo
        self.sesiones = RepositorioSesiones(bd, reloj_ms)
        self.actividad = RegistroActividad(bd, reloj_ms)
        self._hasher = hasher
        self._reloj_s = reloj_s
        self._reloj_ms = reloj_ms
        # 10 cuentas por hora desde una misma IP: frena la creación masiva de cuentas.
        self._limite_registro = limite_registro or LimitadorIntentos(10, 3600)
        # Contraseñas equivocadas: 5 por correo y 20 por IP cada 15 minutos.
        self._fallos_correo = LimitadorIntentos(FALLOS_POR_CORREO, VENTANA_FALLOS, reloj_s)
        self._fallos_ip = LimitadorIntentos(FALLOS_POR_IP, VENTANA_FALLOS, reloj_s)
        # Códigos de 6 dígitos equivocados con la sesión abierta: 5 cada 15 minutos por cuenta.
        self._fallos_codigo = LimitadorIntentos(FALLOS_POR_CORREO, VENTANA_FALLOS, reloj_s)
        # Correos con código: como mucho 5 por hora para una misma cuenta (además de 1 por minuto).
        self._envios_codigo = LimitadorIntentos(5, 3600, reloj_s)

    # ---------- registro ----------

    def registrar(self, datos: DatosRegistro, cliente: Cliente) -> ResultadoRegistro:
        """Crea la cuenta. Si hay enviador de correo, manda el código y la cuenta espera a que lo
        confirmen (sin sesión); si no, abre la primera sesión.

        Raises:
            DemasiadosIntentosError: si esa IP creó demasiadas cuentas hace poco.
            RegistroRechazadoError: si el correo o el documento ya están registrados.
        """
        clave = f"registro:{cliente.ip}"
        espera = self._limite_registro.espera(clave)
        if espera > 0:
            raise DemasiadosIntentosError(espera)
        self._limite_registro.registrar(clave)
        exigir = self._correo is not None
        try:
            usuario = self.usuarios.crear(datos, self._hasher.calcular(datos.contrasena), correo_verificado=not exigir)
        except UsuarioDuplicadoError:
            raise RegistroRechazadoError("Ya existe una cuenta con ese correo o con ese documento") from None
        self.actividad.registrar(usuario.id, TipoActividad.REGISTRO, cliente.ip)
        if exigir:
            return ResultadoRegistro(usuario, token_verificacion=self._enviar_codigo(usuario))
        token, _ = self.sesiones.crear(usuario.id, cliente.ip, cliente.agente)
        self.actividad.registrar(usuario.id, TipoActividad.INICIO_SESION, cliente.ip, cliente.agente)
        return ResultadoRegistro(usuario, token_sesion=token)

    # ---------- confirmar el correo ----------

    def _mandar(self, usuario: Usuario) -> str:
        """Genera un código, lo manda al correo y lo devuelve."""
        assert self._correo is not None
        self._envios_codigo.registrar(f"envio:{usuario.id}")
        codigo = generar_codigo()
        self._correo.enviar(codigo_verificacion(usuario.correo, usuario.nombre, codigo, DURACION_CODIGO // MINUTO))
        return codigo

    def _enviar_codigo(self, usuario: Usuario) -> str:
        """Manda un código nuevo y devuelve el token nuevo de la verificación."""
        return self.verificaciones.nueva(usuario.id, self._mandar(usuario))

    def _puede_enviar(self, usuario_id: int) -> bool:
        return (self.verificaciones.espera_reenvio(usuario_id) == 0
                and self._envios_codigo.espera(f"envio:{usuario_id}") == 0)

    def _token_verificacion(self, usuario: Usuario) -> str:
        """Al intentar entrar sin haber confirmado: manda un código nuevo, salvo que el último sea
        de hace menos de un minuto o ya se hayan enviado 5 en la hora (entonces sigue el de antes)."""
        pendiente = self.verificaciones.de_usuario(usuario.id)
        if self._correo is not None and (pendiente is None or self._puede_enviar(usuario.id)):
            return self._enviar_codigo(usuario)
        if pendiente is None:
            raise VerificacionVencidaError()
        return self.verificaciones.nueva(usuario.id, None)

    def verificar_correo(self, token: str, codigo: str, cliente: Cliente) -> tuple[Usuario, str]:
        """Confirma el correo con el código y abre la sesión.

        Raises:
            VerificacionVencidaError: si no hay verificación con ese token, o el código venció o
                agotó sus 5 intentos (hay que pedir otro).
            CodigoInvalidoError: si el código no es el que se envió (quedan intentos).
        """
        usuario_id = self.verificaciones.usuario_del_token(token)
        if usuario_id is None:
            raise VerificacionVencidaError()
        if not self.verificaciones.comprobar(usuario_id, codigo.replace(" ", "")):
            self.actividad.registrar(usuario_id, TipoActividad.CODIGO_FALLIDO, cliente.ip, "al confirmar el correo")
            vigente = self.verificaciones.de_usuario(usuario_id)
            if vigente is None or vigente.intentos >= INTENTOS_CODIGO or vigente.expira_en <= self._reloj_ms():
                raise VerificacionVencidaError()
            raise CodigoInvalidoError()
        self.verificaciones.borrar(usuario_id)
        self.usuarios.marcar_correo_verificado(usuario_id)
        self.actividad.registrar(usuario_id, TipoActividad.CORREO_VERIFICADO, cliente.ip)
        return self._abrir_sesion(usuario_id, cliente)

    def reenviar_codigo(self, token: str) -> str:
        """Manda otro código al correo de esa verificación (el token sigue sirviendo).
        Devuelve el correo enmascarado.

        Raises:
            VerificacionVencidaError: si el token no corresponde a una verificación.
            EsperaReenvioError: si el último se envió hace menos de un minuto.
            DemasiadosIntentosError: si ya se enviaron 5 en la última hora.
        """
        usuario_id = self.verificaciones.usuario_del_token(token)
        usuario = None if usuario_id is None else self.usuarios.por_id(usuario_id)
        if usuario is None or self._correo is None:
            raise VerificacionVencidaError()
        espera = self.verificaciones.espera_reenvio(usuario.id)
        if espera > 0:
            raise EsperaReenvioError(espera / 1000)
        limite = self._envios_codigo.espera(f"envio:{usuario.id}")
        if limite > 0:
            raise DemasiadosIntentosError(limite)
        self.verificaciones.reemplazar_codigo(usuario.id, self._mandar(usuario))
        return correo_enmascarado(usuario.correo)

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
        if not credenciales.correo_verificado:
            usuario = self.usuarios.por_id(credenciales.usuario_id)
            assert usuario is not None
            return ResultadoInicio(token_verificacion=self._token_verificacion(usuario),
                                   correo=correo_enmascarado(usuario.correo))
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

    # ---------- verificación en dos pasos ----------

    def _codigo_valido(self, credenciales: Credenciales, codigo: str, cliente: Cliente) -> bool:
        """Acepta un código de la app (6 dígitos) o un código de respaldo (que se gasta)."""
        limpio = codigo.replace(" ", "")
        if limpio.isdigit() and len(limpio) == totp.DIGITOS:
            if credenciales.totp_secreto is None:
                return False
            paso = totp.verificar(credenciales.totp_secreto, limpio, self._reloj_s(), credenciales.totp_ultimo_paso)
            return paso is not None and self.usuarios.marcar_paso_totp(credenciales.usuario_id, paso)
        if self.usuarios.usar_codigo(credenciales.usuario_id, hash_codigo(limpio)):
            restantes = self.usuarios.codigos_restantes(credenciales.usuario_id)
            self.actividad.registrar(credenciales.usuario_id, TipoActividad.CODIGO_RESPALDO_USADO, cliente.ip,
                                     f"Quedan {restantes}")
            return True
        return False

    def completar_segundo_paso(self, token_desafio: str, codigo: str, cliente: Cliente) -> tuple[Usuario, str]:
        """Segundo paso del inicio de sesión: el código de la app o uno de respaldo.

        Raises:
            DesafioVencidoError: si el desafío no existe, venció o agotó sus intentos.
            CodigoInvalidoError: si el código no es válido.
        """
        usuario_id = self.sesiones.usuario_del_desafio(token_desafio)
        credenciales = None if usuario_id is None else self.usuarios.credenciales(usuario_id)
        if credenciales is None:
            raise DesafioVencidoError()
        if not self._codigo_valido(credenciales, codigo, cliente):
            self.sesiones.fallo_en_desafio(token_desafio)
            self.actividad.registrar(credenciales.usuario_id, TipoActividad.CODIGO_FALLIDO, cliente.ip)
            raise CodigoInvalidoError()
        self.sesiones.borrar_desafio(token_desafio)
        return self._abrir_sesion(credenciales.usuario_id, cliente, "(con verificación en dos pasos)")

    def _credenciales(self, usuario_id: int) -> Credenciales:
        credenciales = self.usuarios.credenciales(usuario_id)
        if credenciales is None:
            raise OperacionCuentaError("La cuenta no existe")
        return credenciales

    def _exigir_codigo(self, credenciales: Credenciales, codigo: str, cliente: Cliente) -> None:
        clave = f"codigo:{credenciales.usuario_id}"
        espera = self._fallos_codigo.espera(clave)
        if espera > 0:
            raise DemasiadosIntentosError(espera)
        if not self._codigo_valido(credenciales, codigo, cliente):
            self._fallos_codigo.registrar(clave)
            self.actividad.registrar(credenciales.usuario_id, TipoActividad.CODIGO_FALLIDO, cliente.ip)
            raise CodigoInvalidoError()
        self._fallos_codigo.reiniciar(clave)

    def iniciar_dos_pasos(self, usuario_id: int) -> ConfiguracionDosPasos:
        """Genera un secreto nuevo (todavía inactivo) para escanear con la app.

        Raises:
            OperacionCuentaError: si ya está activa.
        """
        credenciales = self._credenciales(usuario_id)
        if credenciales.totp_activo:
            raise OperacionCuentaError("La verificación en dos pasos ya está activa")
        usuario = self.usuarios.por_id(usuario_id)
        assert usuario is not None
        secreto = totp.generar_secreto()
        self.usuarios.guardar_totp(usuario_id, secreto, activo=False)
        return ConfiguracionDosPasos(secreto, totp.uri_otpauth(secreto, usuario.correo))

    def _nuevos_codigos(self, usuario_id: int) -> Lista[str]:
        codigos = generar_codigos()
        hashes: Lista[bytes] = Lista()
        for codigo in codigos:
            hashes.agregar(hash_codigo(codigo))
        self.usuarios.reemplazar_codigos(usuario_id, hashes)
        return codigos

    def confirmar_dos_pasos(self, usuario_id: int, codigo: str, cliente: Cliente) -> Lista[str]:
        """Activa la verificación si el código de la app es correcto.

        Returns:
            Los 10 códigos de respaldo (se muestran una sola vez).
        """
        credenciales = self._credenciales(usuario_id)
        if credenciales.totp_activo:
            raise OperacionCuentaError("La verificación en dos pasos ya está activa")
        if credenciales.totp_secreto is None:
            raise OperacionCuentaError("Primero genera el código QR")
        if not codigo.replace(" ", "").isdigit():
            raise CodigoInvalidoError()
        self._exigir_codigo(credenciales, codigo, cliente)
        self.usuarios.guardar_totp(usuario_id, credenciales.totp_secreto, activo=True)
        paso = totp.paso(self._reloj_s())
        self.usuarios.marcar_paso_totp(usuario_id, paso)
        self.actividad.registrar(usuario_id, TipoActividad.DOS_PASOS_ACTIVADA, cliente.ip)
        return self._nuevos_codigos(usuario_id)

    def desactivar_dos_pasos(self, usuario_id: int, contrasena: str, codigo: str, cliente: Cliente) -> None:
        """Pide la contraseña y un código (de la app o de respaldo) para desactivarla."""
        credenciales = self._credenciales(usuario_id)
        if not credenciales.totp_activo:
            raise OperacionCuentaError("La verificación en dos pasos no está activa")
        if not self._hasher.verificar(credenciales.contrasena_hash, contrasena):
            raise CredencialesInvalidasError()
        self._exigir_codigo(credenciales, codigo, cliente)
        self.usuarios.guardar_totp(usuario_id, None, activo=False)
        self.usuarios.reemplazar_codigos(usuario_id, Lista())
        self.actividad.registrar(usuario_id, TipoActividad.DOS_PASOS_DESACTIVADA, cliente.ip)

    def regenerar_codigos(self, usuario_id: int, codigo: str, cliente: Cliente) -> Lista[str]:
        """Invalida los códigos de respaldo anteriores y entrega 10 nuevos."""
        credenciales = self._credenciales(usuario_id)
        if not credenciales.totp_activo:
            raise OperacionCuentaError("La verificación en dos pasos no está activa")
        self._exigir_codigo(credenciales, codigo, cliente)
        self.actividad.registrar(usuario_id, TipoActividad.CODIGOS_REGENERADOS, cliente.ip)
        return self._nuevos_codigos(usuario_id)

    # ---------- sesiones ----------

    def sesion_actual(self, token: str | None) -> tuple[Usuario, Sesion]:
        """El usuario y la sesión del token de la cookie.

        Raises:
            SesionInvalidaError: si no hay token, venció o se cerró.
        """
        sesion = None if not token else self.sesiones.validar(token)
        usuario = None if sesion is None else self.usuarios.por_id(sesion.usuario_id)
        if sesion is None or usuario is None:
            raise SesionInvalidaError()
        return usuario, sesion

    def cerrar_sesion(self, token: str, cliente: Cliente) -> None:
        """Cierra la sesión del token si sigue vigente; si ya no existe, no hace nada."""
        sesion = self.sesiones.validar(token)
        if sesion is not None and self.sesiones.cerrar_token(token):
            self.actividad.registrar(sesion.usuario_id, TipoActividad.CIERRE_SESION, cliente.ip)

    def sesiones_activas(self, usuario_id: int) -> Lista[Sesion]:
        """Sesiones abiertas del usuario, la más reciente primero."""
        return self.sesiones.activas(usuario_id)

    def cerrar_otra_sesion(self, usuario_id: int, sesion_id: int, cliente: Cliente) -> None:
        """Cierra una sesión propia por su id (por ejemplo, la de un dispositivo perdido)."""
        if not self.sesiones.cerrar(usuario_id, sesion_id):
            raise OperacionCuentaError("No existe una sesión abierta con ese id")
        self.actividad.registrar(usuario_id, TipoActividad.SESIONES_CERRADAS, cliente.ip, f"Sesión {sesion_id}")

    def cerrar_otras_sesiones(self, usuario_id: int, actual: int, cliente: Cliente) -> int:
        """Cierra todas las sesiones menos la actual. Returns: cuántas cerró."""
        cerradas = self.sesiones.cerrar_todas(usuario_id, excepto=actual)
        if cerradas:
            self.actividad.registrar(usuario_id, TipoActividad.SESIONES_CERRADAS, cliente.ip, f"{cerradas} sesiones")
        return cerradas

    def actividad_reciente(self, usuario_id: int, limite: int = 50) -> Lista[EventoActividad]:
        """Últimos eventos de seguridad del usuario (inicios de sesión, códigos fallidos, cambios)."""
        return self.actividad.recientes(usuario_id, limite)

    # ---------- contraseña ----------

    def cambiar_contrasena(self, usuario_id: int, actual: str, nueva: str, sesion_actual: int,
                           cliente: Cliente) -> None:
        """Cambia la contraseña y cierra las demás sesiones (por si alguien más la conocía).

        Raises:
            CredencialesInvalidasError: si la contraseña actual no coincide.
            DatoInvalidoError: si la nueva no cumple la política o es igual a la actual.
        """
        credenciales = self._credenciales(usuario_id)
        clave = f"contrasena:{usuario_id}"
        espera = self._fallos_codigo.espera(clave)
        if espera > 0:
            raise DemasiadosIntentosError(espera)
        if not self._hasher.verificar(credenciales.contrasena_hash, actual):
            self._fallos_codigo.registrar(clave)
            raise CredencialesInvalidasError()
        if nueva == actual:
            raise DatoInvalidoError("contrasenaNueva", "La contraseña nueva debe ser distinta de la actual")
        usuario = self.usuarios.por_id(usuario_id)
        assert usuario is not None
        problemas = problemas_contrasena(nueva, (usuario.nombre, usuario.apellido, usuario.correo,
                                                 usuario.numero_documento))
        if not problemas.esta_vacia():
            raise DatoInvalidoError("contrasenaNueva", problemas.primero())
        self.usuarios.cambiar_contrasena(usuario_id, self._hasher.calcular(nueva))
        self.sesiones.cerrar_todas(usuario_id, excepto=sesion_actual)
        self.actividad.registrar(usuario_id, TipoActividad.CONTRASENA_CAMBIADA, cliente.ip)
