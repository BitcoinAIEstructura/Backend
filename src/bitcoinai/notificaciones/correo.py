"""Envío de correos: por SMTP (Gmail u otro), a una carpeta local o a la memoria (pruebas).

La contraseña SMTP se lee del entorno aquí mismo y no se guarda en ``Configuracion``,
para que nunca aparezca en registros ni en mensajes de error. Del correo enviado solo
se registra que se envió (nunca el destinatario ni el contenido: el código es secreto).
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Protocol

from bitcoinai.estructuras import Lista

LOG = logging.getLogger("bitcoinai.correo")

NOMBRE_REMITENTE = "Nexabit"



def es_limite_de_envios(error: smtplib.SMTPResponseException) -> bool:
    """Si el servidor dice "llegaste al límite de envíos" (Gmail: ``550 5.4.5 Daily user sending limit``)."""
    texto = error.smtp_error if isinstance(error.smtp_error, bytes) else str(error.smtp_error).encode()
    return error.smtp_code in (421, 550) and (b"5.4.5" in texto or b"limit" in texto.lower())


@dataclass(frozen=True, slots=True)
class MensajeCorreo:
    destino: str
    asunto: str
    texto: str
    html: str


class EnviadorCorreo(Protocol):
    """Quien entrega los correos. ``enviar`` no debe bloquear la petición HTTP."""

    def enviar(self, mensaje: MensajeCorreo) -> None: ...

    def descripcion(self) -> str:
        """Cómo se envían, para el registro al arrancar (sin secretos)."""
        ...


def armar(mensaje: MensajeCorreo, remitente: str) -> EmailMessage:
    """El correo con versión de texto y versión HTML (los programas de correo eligen)."""
    correo = EmailMessage()
    correo["From"] = formataddr((NOMBRE_REMITENTE, remitente))
    correo["To"] = mensaje.destino
    correo["Subject"] = mensaje.asunto
    correo["Message-ID"] = make_msgid(domain=remitente.rsplit("@", 1)[-1] or "nexabit.local")
    correo.set_content(mensaje.texto)
    correo.add_alternative(mensaje.html, subtype="html")
    return correo


@dataclass(frozen=True)
class DatosSmtp:
    """Servidor SMTP. ``repr`` no muestra la contraseña."""

    host: str
    puerto: int
    usuario: str
    contrasena: str = field(repr=False)
    remitente: str

    @classmethod
    def desde_entorno(cls, entorno: Mapping[str, str] | None = None) -> DatosSmtp | None:
        """``SMTP_USUARIO`` y ``SMTP_CONTRASENA`` (para Gmail, una contraseña de aplicación).

        Opcionales: ``SMTP_HOST`` (smtp.gmail.com), ``SMTP_PUERTO`` (587) y ``CORREO_REMITENTE``
        (por defecto, el mismo usuario). Sin usuario o contraseña devuelve None.

        Raises:
            ValueError: si ``SMTP_PUERTO`` no es un número válido.
        """
        variables = os.environ if entorno is None else entorno
        usuario = variables.get("SMTP_USUARIO", "").strip()
        # Google muestra la contraseña de aplicación en grupos con espacios: se quitan.
        contrasena = variables.get("SMTP_CONTRASENA", "").replace(" ", "").strip()
        if not usuario or not contrasena:
            return None
        texto_puerto = variables.get("SMTP_PUERTO", "").strip() or "587"
        if not texto_puerto.isdigit() or not 1 <= int(texto_puerto) <= 65_535:
            raise ValueError(f"SMTP_PUERTO debe ser un número entre 1 y 65535: {texto_puerto}")
        return cls(host=variables.get("SMTP_HOST", "").strip() or "smtp.gmail.com", puerto=int(texto_puerto),
                   usuario=usuario, contrasena=contrasena,
                   remitente=variables.get("CORREO_REMITENTE", "").strip() or usuario)


class CorreoSmtp:
    """Envía por SMTP con STARTTLS (puerto 587) o TLS directo (puerto 465), en un hilo aparte.

    Así la petición de registro responde enseguida aunque el servidor de correo tarde.
    Si el envío falla, se registra el error sin datos personales; la persona puede pedir
    que se lo reenvíen.
    """

    def __init__(self, datos: DatosSmtp, espera_s: float = 20) -> None:
        self._datos = datos
        self._espera_s = espera_s

    def descripcion(self) -> str:
        return (f"SMTP {self._datos.host}:{self._datos.puerto} desde {self._datos.remitente} "
                "hacia el correo de cada persona que se registra")

    def enviar(self, mensaje: MensajeCorreo) -> None:
        threading.Thread(target=self.enviar_ahora, args=(mensaje,), name="correo", daemon=True).start()

    def enviar_ahora(self, mensaje: MensajeCorreo) -> bool:
        """Envía y espera. Devuelve si se pudo (nunca lanza excepciones)."""
        d = self._datos
        contexto = ssl.create_default_context()
        try:
            if d.puerto == 465:
                with smtplib.SMTP_SSL(d.host, d.puerto, timeout=self._espera_s, context=contexto) as smtp:
                    smtp.login(d.usuario, d.contrasena)
                    smtp.send_message(armar(mensaje, d.remitente))
            else:
                with smtplib.SMTP(d.host, d.puerto, timeout=self._espera_s) as smtp:
                    smtp.starttls(context=contexto)
                    smtp.login(d.usuario, d.contrasena)
                    smtp.send_message(armar(mensaje, d.remitente))
        except smtplib.SMTPAuthenticationError:
            LOG.error("No se pudo enviar un correo: Gmail rechazó el usuario o la contraseña de aplicación "
                      "(revisa SMTP_USUARIO y SMTP_CONTRASENA)")
            return False
        except smtplib.SMTPRecipientsRefused:
            # El error trae la dirección: no se registra.
            LOG.warning("No se pudo enviar un correo: el servidor rechazó la dirección de destino")
            return False
        except smtplib.SMTPResponseException as error:
            if es_limite_de_envios(error):
                LOG.error("No se pudo enviar un correo: se llegó al límite diario de envíos de la cuenta "
                          "(en Gmail, unos 500 al día); se reinicia en 24 horas")
            else:
                LOG.error("No se pudo enviar un correo: el servidor respondió %d", error.smtp_code)
            return False
        except (OSError, smtplib.SMTPException) as error:
            LOG.error("No se pudo enviar un correo: %s", type(error).__name__)
            return False
        # Ni el asunto (lleva el código) ni el destinatario.
        LOG.info("Correo enviado")
        return True


class BuzonLocal:
    """Para desarrollo sin SMTP: cada correo se guarda como archivo .eml en una carpeta.

    Se abre con cualquier programa de correo (o con el Bloc de notas). La carpeta está
    dentro de DATA_DIR, que no se sube a git.
    """

    def __init__(self, carpeta: str) -> None:
        self._carpeta = Path(carpeta)

    def descripcion(self) -> str:
        return f"sin SMTP: los correos se guardan en {self._carpeta}"

    def enviar(self, mensaje: MensajeCorreo) -> None:
        self._carpeta.mkdir(parents=True, exist_ok=True)
        nombre = f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1_000_000:06d}.eml"
        (self._carpeta / nombre).write_bytes(bytes(armar(mensaje, "no-responder@nexabit.local")))
        LOG.info("Correo guardado en %s", self._carpeta / nombre)


class BuzonMemoria:
    """Guarda los correos en memoria (para las pruebas)."""

    def __init__(self) -> None:
        self.enviados: Lista[MensajeCorreo] = Lista()

    def descripcion(self) -> str:
        return "en memoria"

    def enviar(self, mensaje: MensajeCorreo) -> None:
        self.enviados.agregar(mensaje)

    def ultimo(self) -> MensajeCorreo:
        return self.enviados.ultimo()


def enviador_desde_entorno(data_dir: str, entorno: Mapping[str, str] | None = None) -> EnviadorCorreo:
    """SMTP si están ``SMTP_USUARIO`` y ``SMTP_CONTRASENA``; si no, la carpeta ``<DATA_DIR>/correos``."""
    datos = DatosSmtp.desde_entorno(entorno)
    if datos is not None:
        if datos.host == "smtp.gmail.com" and datos.remitente.lower() != datos.usuario.lower():
            # Gmail solo firma como la cuenta que inicia sesión (o un alias verificado en ella):
            # con otro remitente, Hotmail, Outlook y otros suelen mandar el correo a spam.
            LOG.warning("CORREO_REMITENTE es distinto de SMTP_USUARIO: con Gmail, déjalo vacío o pon un alias "
                        "verificado en esa cuenta, o los correos pueden llegar a spam")
        return CorreoSmtp(datos)
    return BuzonLocal(f"{data_dir.rstrip('/')}/correos")
