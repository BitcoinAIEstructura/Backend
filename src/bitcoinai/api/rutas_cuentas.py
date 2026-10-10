"""Endpoints de cuentas: registro, inicio y cierre de sesión.

- POST /api/cuentas/registro, GET /api/cuentas/yo
- POST /api/sesion, POST /api/sesion/codigo, DELETE /api/sesion

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
from bitcoinai.usuarios.modelo import DatosRegistro, Usuario
from bitcoinai.usuarios.servicio import Cliente, ServicioCuentas
from bitcoinai.usuarios.sesiones import DURACION_DESAFIO, DURACION_SESION, Sesion

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


def crear_rutas_cuentas(servicio: ServicioCuentas, config: Configuracion) -> APIRouter:
    rutas = APIRouter()
    cookies = Cookies(config)

    def abrir(respuesta: Response, usuario: Usuario, token: str) -> dict[str, Any]:
        cookies.poner(respuesta, cookies.sesion, token, DURACION_SESION // 1000)
        cookies.borrar(respuesta, cookies.desafio)
        return {"usuario": usuario_a_json(usuario)}

    @rutas.post("/api/cuentas/registro", status_code=201)
    def registrar(cuerpo: CuerpoRegistro, peticion: Request, respuesta: Response) -> dict[str, Any]:
        """Crea la cuenta y deja la sesión abierta."""
        datos = DatosRegistro.validar(cuerpo.nombre, cuerpo.apellido, cuerpo.correo, cuerpo.tipo_documento,
                                      cuerpo.numero_documento, cuerpo.telefono, cuerpo.contrasena)
        usuario, token = servicio.registrar(datos, cliente_de(peticion, config))
        return abrir(respuesta, usuario, token)

    @rutas.post("/api/sesion")
    def iniciar(cuerpo: CuerpoInicio, peticion: Request, respuesta: Response) -> dict[str, Any]:
        """Correo y contraseña. Con verificación en dos pasos responde ``{"segundoPaso": true}``
        y hay que enviar el código a POST /api/sesion/codigo."""
        resultado = servicio.iniciar_sesion(cuerpo.correo, cuerpo.contrasena, cliente_de(peticion, config))
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

    return rutas
