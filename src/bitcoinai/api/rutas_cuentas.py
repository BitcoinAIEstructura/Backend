"""Endpoints de cuentas: registro, sesión y centro de seguridad.

- POST /api/cuentas/registro, GET /api/cuentas/yo
- POST /api/sesion, POST /api/sesion/codigo, DELETE /api/sesion
- Verificación en dos pasos: POST /api/cuentas/dos-pasos, …/confirmar, …/desactivar, …/codigos
- GET /api/cuentas/sesiones, DELETE /api/cuentas/sesiones/{id}, POST /api/cuentas/sesiones/cerrar-otras
- GET /api/cuentas/actividad, POST /api/cuentas/contrasena

La sesión viaja en una cookie ``HttpOnly`` (el JavaScript de la página no la
puede leer, así un script inyectado no puede robarla) y ``SameSite=Strict`` (no
se envía desde otros sitios, lo que bloquea la falsificación de peticiones).
Con ``COOKIE_SEGURA`` además es ``Secure`` (solo por HTTPS) y usa el prefijo
``__Host-``, que impide que un subdominio la reemplace.
"""

from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.errores import ApiError
from bitcoinai.usuarios.modelo import DatosRegistro, Usuario
from bitcoinai.usuarios.servicio import Cliente, ServicioCuentas
from bitcoinai.usuarios.sesiones import DURACION_DESAFIO, DURACION_SESION, Sesion
from bitcoinai.usuarios.verificacion import DURACION_CODIGO

LARGO_TEXTO = 200


class CuerpoRegistro(BaseModel):
    """``{nombre, apellido, correo, tipoDocumento: "CC"|"CE", numeroDocumento, telefono, contrasena}``."""

    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)

    nombre: str = Field(max_length=LARGO_TEXTO)
    apellido: str = Field(max_length=LARGO_TEXTO)
    correo: str = Field(max_length=LARGO_TEXTO)
    tipo_documento: str = Field(alias="tipoDocumento", max_length=10)
    numero_documento: str = Field(alias="numeroDocumento", max_length=40)
    telefono: str = Field(max_length=40)
    contrasena: str = Field(max_length=256)


class CuerpoInicio(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    correo: str = Field(max_length=LARGO_TEXTO)
    contrasena: str = Field(max_length=256)


class CuerpoCodigo(BaseModel):
    """Código de 6 dígitos de la app, o un código de respaldo ``XXXXX-XXXXX``."""

    model_config = ConfigDict(strict=True, extra="forbid")

    codigo: str = Field(max_length=20)


class CuerpoDesactivar(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    contrasena: str = Field(max_length=256)
    codigo: str = Field(max_length=20)


class CuerpoContrasena(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)

    contrasena_actual: str = Field(alias="contrasenaActual", max_length=256)
    contrasena_nueva: str = Field(alias="contrasenaNueva", max_length=256)


def usuario_a_json(usuario: Usuario) -> dict[str, Any]:
    """Datos públicos de la cuenta: el documento y el teléfono van enmascarados."""
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "correo": usuario.correo,
        "tipoDocumento": usuario.tipo_documento.name,
        "documento": usuario.documento_enmascarado,
        "telefono": usuario.telefono_enmascarado,
        "verificacionDosPasos": usuario.verificacion_dos_pasos,
        "creadoEn": usuario.creado_en,
    }


class Cookies:
    """Nombres y atributos de las cookies según la configuración."""

    def __init__(self, config: Configuracion) -> None:
        self.segura = config.cookie_segura
        prefijo = "__Host-" if self.segura else ""
        self.sesion = f"{prefijo}sesion"
        self.desafio = f"{prefijo}desafio"
        # Confirmar el correo: dice a qué cuenta va el código sin poner el correo en la URL.
        # Dura un día: la persona puede volver más tarde y pedir otro código.
        self.verificacion = f"{prefijo}verificacion"

    def poner(self, respuesta: Response, nombre: str, valor: str, segundos: int) -> None:
        respuesta.set_cookie(nombre, valor, max_age=segundos, path="/", secure=self.segura, httponly=True,
                             samesite="strict")

    def borrar(self, respuesta: Response, nombre: str) -> None:
        respuesta.delete_cookie(nombre, path="/", secure=self.segura, httponly=True, samesite="strict")


def cliente_de(peticion: Request, config: Configuracion) -> Cliente:
    """IP y navegador de quien pide. ``X-Forwarded-For`` solo se cree con ``CONFIAR_PROXY``
    (si no, cualquiera podría inventarse una IP para saltarse los límites)."""
    ip = peticion.client.host if peticion.client else "desconocida"
    if config.confiar_proxy:
        reenviada = peticion.headers.get("x-forwarded-for", "").split(",")[0].strip()
        ip = reenviada or ip
    return Cliente(ip[:64], peticion.headers.get("user-agent", "desconocido")[:200])


def sesion_de(peticion: Request, servicio: ServicioCuentas, cookies: Cookies) -> tuple[Usuario, Sesion]:
    """Usuario y sesión de la cookie, o 401 (``SesionInvalidaError``)."""
    return servicio.sesion_actual(peticion.cookies.get(cookies.sesion))


DURACION_VERIFICACION = 24 * 60 * 60
"""Segundos que dura la cookie de la verificación del correo (el código vence antes: 15 min)."""
assert DURACION_CODIGO // 1000 < DURACION_VERIFICACION


def crear_rutas_cuentas(servicio: ServicioCuentas, config: Configuracion) -> APIRouter:
    rutas = APIRouter()
    cookies = Cookies(config)

    def abrir(respuesta: Response, usuario: Usuario, token: str) -> dict[str, Any]:
        cookies.poner(respuesta, cookies.sesion, token, DURACION_SESION // 1000)
        cookies.borrar(respuesta, cookies.desafio)
        cookies.borrar(respuesta, cookies.verificacion)
        return {"usuario": usuario_a_json(usuario)}

    def es_demo(usuario: Usuario) -> bool:
        return bool(config.demo_correo) and usuario.correo.lower() == config.demo_correo

    def con_seguridad_editable(peticion: Request) -> tuple[Usuario, Sesion]:
        """La sesión, si la cuenta puede cambiar su seguridad (la de demostración no)."""
        usuario, sesion = sesion_de(peticion, servicio, cookies)
        if es_demo(usuario):
            raise ApiError(403, "La cuenta de demostración no puede cambiar su seguridad. "
                                "Crea tu propia cuenta para probarlo.")
        return usuario, sesion

    def pedir_codigo(respuesta: Response, token: str, correo: str) -> dict[str, Any]:
        cookies.poner(respuesta, cookies.verificacion, token, DURACION_VERIFICACION)
        return {"verificarCorreo": True, "correo": correo}

    @rutas.post("/api/cuentas/registro", status_code=201)
    def registrar(cuerpo: CuerpoRegistro, peticion: Request, respuesta: Response) -> dict[str, Any]:
        """Crea la cuenta. Si hay que confirmar el correo responde ``{"verificarCorreo": true, "correo"}``
        (el código llega al correo y se envía a POST /api/cuentas/verificar-correo); si no, deja la
        sesión abierta y responde ``{"usuario"}``."""
        datos = DatosRegistro.validar(cuerpo.nombre, cuerpo.apellido, cuerpo.correo, cuerpo.tipo_documento,
                                      cuerpo.numero_documento, cuerpo.telefono, cuerpo.contrasena)
        resultado = servicio.registrar(datos, cliente_de(peticion, config))
        if resultado.token_verificacion is not None:
            return pedir_codigo(respuesta, resultado.token_verificacion, resultado.correo)
        return {"verificarCorreo": False, **abrir(respuesta, *resultado.sesion())}

    @rutas.post("/api/cuentas/verificar-correo")
    def verificar_correo(cuerpo: CuerpoCodigo, peticion: Request, respuesta: Response) -> dict[str, Any]:
        """El código de 6 dígitos que llegó al correo: confirma la cuenta y abre la sesión."""
        token = peticion.cookies.get(cookies.verificacion, "")
        usuario, sesion = servicio.verificar_correo(token, cuerpo.codigo, cliente_de(peticion, config))
        return abrir(respuesta, usuario, sesion)

    @rutas.post("/api/cuentas/reenviar-codigo")
    def reenviar_codigo(peticion: Request) -> dict[str, Any]:
        """Manda otro código al correo (uno por minuto y 5 por hora)."""
        return {"correo": servicio.reenviar_codigo(peticion.cookies.get(cookies.verificacion, ""))}

    @rutas.post("/api/sesion")
    def iniciar(cuerpo: CuerpoInicio, peticion: Request, respuesta: Response) -> dict[str, Any]:
        """Correo y contraseña. Con verificación en dos pasos responde ``{"segundoPaso": true}``
        y hay que enviar el código a POST /api/sesion/codigo."""
        resultado = servicio.iniciar_sesion(cuerpo.correo, cuerpo.contrasena, cliente_de(peticion, config))
        if resultado.token_verificacion is not None and resultado.correo is not None:
            return {"segundoPaso": False, **pedir_codigo(respuesta, resultado.token_verificacion, resultado.correo)}
        if resultado.token_desafio is not None:
            cookies.poner(respuesta, cookies.desafio, resultado.token_desafio, DURACION_DESAFIO // 1000)
            return {"segundoPaso": True}
        assert resultado.usuario is not None and resultado.token_sesion is not None
        return {"segundoPaso": False, **abrir(respuesta, resultado.usuario, resultado.token_sesion)}

    @rutas.post("/api/sesion/codigo")
    def segundo_paso(cuerpo: CuerpoCodigo, peticion: Request, respuesta: Response) -> dict[str, Any]:
        """Código de la app (o de respaldo) para terminar de iniciar sesión."""
        desafio = peticion.cookies.get(cookies.desafio, "")
        usuario, token = servicio.completar_segundo_paso(desafio, cuerpo.codigo, cliente_de(peticion, config))
        return abrir(respuesta, usuario, token)

    @rutas.get("/api/cuentas/demo")
    def demo_disponible() -> dict[str, Any]:
        """Si el servidor tiene cuenta de demostración (para mostrar el botón «Entrar a la demo»)."""
        return {"disponible": bool(config.demo_correo)}

    @rutas.post("/api/cuentas/demo")
    def entrar_demo(peticion: Request, respuesta: Response) -> dict[str, Any]:
        """Abre la cuenta de demostración sin contraseña (404 si el servidor no tiene una)."""
        abierta = servicio.iniciar_demo(config.demo_correo, cliente_de(peticion, config)) \
            if config.demo_correo else None
        if abierta is None:
            raise ApiError(404, "La demo no está disponible en este momento")
        return abrir(respuesta, *abierta)

    @rutas.delete("/api/sesion", status_code=204)
    def cerrar(peticion: Request, respuesta: Response) -> None:
        """Cierra la sesión de este dispositivo (no falla si ya estaba cerrada)."""
        token = peticion.cookies.get(cookies.sesion)
        if token:
            servicio.cerrar_sesion(token, cliente_de(peticion, config))
        cookies.borrar(respuesta, cookies.sesion)

    @rutas.get("/api/cuentas/yo")
    def yo(peticion: Request) -> dict[str, Any]:
        """La cuenta de la sesión actual (401 si no hay sesión)."""
        usuario, _ = sesion_de(peticion, servicio, cookies)
        return {"usuario": usuario_a_json(usuario)}

    # ---------- centro de seguridad ----------

    @rutas.post("/api/cuentas/dos-pasos")
    def iniciar_dos_pasos(peticion: Request) -> dict[str, Any]:
        """Secreto nuevo y enlace ``otpauth://`` para mostrar como código QR."""
        usuario, _ = con_seguridad_editable(peticion)
        configuracion = servicio.iniciar_dos_pasos(usuario.id)
        return {"secreto": configuracion.secreto, "uri": configuracion.uri}

    @rutas.post("/api/cuentas/dos-pasos/confirmar")
    def confirmar_dos_pasos(cuerpo: CuerpoCodigo, peticion: Request) -> dict[str, Any]:
        """Activa la verificación con el primer código de la app; devuelve los códigos de respaldo."""
        usuario, _ = con_seguridad_editable(peticion)
        codigos = servicio.confirmar_dos_pasos(usuario.id, cuerpo.codigo, cliente_de(peticion, config))
        return {"codigosRespaldo": list(codigos)}

    @rutas.post("/api/cuentas/dos-pasos/desactivar", status_code=204)
    def desactivar_dos_pasos(cuerpo: CuerpoDesactivar, peticion: Request) -> None:
        """Apaga la verificación en dos pasos; exige la contraseña y un código válido."""
        usuario, _ = con_seguridad_editable(peticion)
        servicio.desactivar_dos_pasos(usuario.id, cuerpo.contrasena, cuerpo.codigo, cliente_de(peticion, config))

    @rutas.post("/api/cuentas/dos-pasos/codigos")
    def regenerar_codigos(cuerpo: CuerpoCodigo, peticion: Request) -> dict[str, Any]:
        """Diez códigos de respaldo nuevos; los anteriores dejan de servir."""
        usuario, _ = con_seguridad_editable(peticion)
        codigos = servicio.regenerar_codigos(usuario.id, cuerpo.codigo, cliente_de(peticion, config))
        return {"codigosRespaldo": list(codigos)}

    @rutas.get("/api/cuentas/sesiones")
    def sesiones(peticion: Request) -> dict[str, Any]:
        """Sesiones abiertas (dispositivos), la más reciente primero; ``actual`` marca esta."""
        usuario, actual = sesion_de(peticion, servicio, cookies)
        return {"sesiones": [sesion_a_json(s, s.id == actual.id) for s in servicio.sesiones_activas(usuario.id)]}

    @rutas.delete("/api/cuentas/sesiones/{sesion_id}", status_code=204)
    def cerrar_una(sesion_id: int, peticion: Request) -> None:
        """Cierra una sesión de otro dispositivo por su id (la sesión actual no se puede cerrar así)."""
        usuario, _ = con_seguridad_editable(peticion)
        servicio.cerrar_otra_sesion(usuario.id, sesion_id, cliente_de(peticion, config))

    @rutas.post("/api/cuentas/sesiones/cerrar-otras")
    def cerrar_otras(peticion: Request) -> dict[str, Any]:
        """Cierra la sesión en todos los demás dispositivos."""
        usuario, actual = con_seguridad_editable(peticion)
        return {"cerradas": servicio.cerrar_otras_sesiones(usuario.id, actual.id, cliente_de(peticion, config))}

    @rutas.get("/api/cuentas/actividad")
    def actividad(peticion: Request, limite: int = 50) -> dict[str, Any]:
        """Actividad de seguridad reciente (de 1 a 200 eventos)."""
        usuario, _ = sesion_de(peticion, servicio, cookies)
        eventos = servicio.actividad_reciente(usuario.id, max(1, min(limite, 200)))
        return {"eventos": [{"momento": e.momento, "tipo": e.tipo.name, "descripcion": e.tipo.value, "ip": e.ip,
                             "detalle": e.detalle} for e in eventos]}

    @rutas.post("/api/cuentas/contrasena", status_code=204)
    def cambiar_contrasena(cuerpo: CuerpoContrasena, peticion: Request) -> None:
        """Cambia la contraseña y cierra las demás sesiones."""
        usuario, actual = con_seguridad_editable(peticion)
        servicio.cambiar_contrasena(usuario.id, cuerpo.contrasena_actual, cuerpo.contrasena_nueva, actual.id,
                                    cliente_de(peticion, config))

    return rutas


def sesion_a_json(sesion: Sesion, actual: bool) -> dict[str, Any]:
    """Sesión abierta tal como la ve el centro de seguridad (``actual`` marca la de este dispositivo)."""
    return {"id": sesion.id, "actual": actual, "ip": sesion.ip, "agente": sesion.agente,
            "creadaEn": sesion.creada_en, "ultimaActividad": sesion.ultima_actividad, "expiraEn": sesion.expira_en}
