import json
import logging
import smtplib
from email import message_from_bytes, policy
from pathlib import Path
from typing import Any

import httpx
import pytest

from bitcoinai.notificaciones import BuzonLocal, BuzonMemoria, CorreoSmtp, DatosSmtp, enviador_desde_entorno
from bitcoinai.notificaciones.correo import URL_BREVO, CorreoBrevo, DatosBrevo, MensajeCorreo, armar
from bitcoinai.notificaciones.plantillas import codigo_verificacion


def test_plantilla_del_codigo_escapa_el_nombre() -> None:
    m = codigo_verificacion("ana@correo.co", "<b>Ana</b>", "042137", 15)
    assert m.asunto == "042137 es tu código para activar Nexabit"
    assert "Hola, <b>Ana</b>" in m.texto and "&lt;b&gt;Ana&lt;/b&gt;" in m.html and "<b>Ana</b>" not in m.html
    assert "042137" in m.html and "15 minutos" in m.html


def test_datos_smtp_desde_el_entorno() -> None:
    assert DatosSmtp.desde_entorno({}) is None
    assert DatosSmtp.desde_entorno({"SMTP_USUARIO": "grupo@gmail.com"}) is None
    d = DatosSmtp.desde_entorno({"SMTP_USUARIO": "grupo@gmail.com", "SMTP_CONTRASENA": "abcd efgh ijkl mnop"})
    assert d is not None
    assert (d.host, d.puerto, d.contrasena, d.remitente) == ("smtp.gmail.com", 587, "abcdefghijklmnop",
                                                            "grupo@gmail.com")
    assert "abcd" not in repr(d)  # la contraseña nunca sale en registros
    with pytest.raises(ValueError, match="SMTP_PUERTO"):
        DatosSmtp.desde_entorno({"SMTP_USUARIO": "a@b.co", "SMTP_CONTRASENA": "x", "SMTP_PUERTO": "correo"})


def test_sin_smtp_los_correos_van_a_una_carpeta(tmp_path: Path) -> None:
    enviador = enviador_desde_entorno(str(tmp_path), {})
    assert isinstance(enviador, BuzonLocal) and "correos" in enviador.descripcion()
    enviador.enviar(codigo_verificacion("ana@correo.co", "Ana", "123456", 15))
    [archivo] = (tmp_path / "correos").glob("*.eml")
    correo = message_from_bytes(archivo.read_bytes(), policy=policy.default)
    assert correo["To"] == "ana@correo.co" and "Nexabit" in correo["From"]
    assert correo.get_body(("html",)) is not None and correo.get_body(("plain",)) is not None


def test_con_smtp_usa_gmail(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    enviador = enviador_desde_entorno(str(tmp_path), {"SMTP_USUARIO": "g@gmail.com", "SMTP_CONTRASENA": "x"})
    assert isinstance(enviador, CorreoSmtp) and "smtp.gmail.com:587" in enviador.descripcion()
    assert "cada persona que se registra" in enviador.descripcion()
    assert "CORREO_REMITENTE" not in caplog.text
    # Con Gmail, otro remitente distinto de la cuenta hace que el correo llegue a spam: se avisa.
    enviador_desde_entorno(str(tmp_path), {"SMTP_USUARIO": "g@gmail.com", "SMTP_CONTRASENA": "x",
                                           "CORREO_REMITENTE": "no-responder@nexabit.co"})
    assert "CORREO_REMITENTE es distinto" in caplog.text


class SmtpFalso:
    """Imita smtplib.SMTP y anota lo que se hizo."""

    hechos: list[str] = []
    falla_login = False
    error_envio: Exception | None = None

    def __init__(self, host: str, puerto: int, timeout: float) -> None:
        SmtpFalso.hechos.append(f"conectar {host}:{puerto}")

    def __enter__(self) -> "SmtpFalso":
        return self

    def __exit__(self, *_: Any) -> None:
        SmtpFalso.hechos.append("cerrar")

    def starttls(self, context: Any) -> None:
        SmtpFalso.hechos.append("starttls")

    def login(self, usuario: str, contrasena: str) -> None:
        if SmtpFalso.falla_login:
            raise smtplib.SMTPAuthenticationError(535, b"no")
        SmtpFalso.hechos.append(f"login {usuario}")

    def send_message(self, mensaje: Any) -> None:
        if SmtpFalso.error_envio is not None:
            raise SmtpFalso.error_envio
        SmtpFalso.hechos.append(f"enviar a {mensaje['To']}")


def test_smtp_con_starttls_y_errores_sin_lanzar(monkeypatch: pytest.MonkeyPatch,
                                                caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
    caplog.set_level(logging.INFO)
    SmtpFalso.hechos = []
    enviador = CorreoSmtp(DatosSmtp("smtp.gmail.com", 587, "g@gmail.com", "secreta", "g@gmail.com"))
    mensaje = codigo_verificacion("ana@correo.co", "Ana", "123456", 15)
    assert enviador.enviar_ahora(mensaje) is True
    assert SmtpFalso.hechos == ["conectar smtp.gmail.com:587", "starttls", "login g@gmail.com",
                                "enviar a ana@correo.co", "cerrar"]
    SmtpFalso.falla_login = True
    try:
        assert enviador.enviar_ahora(mensaje) is False
    finally:
        SmtpFalso.falla_login = False
    registro = caplog.text
    assert "Correo enviado" in registro and "contraseña de aplicación" in registro
    assert "secreta" not in registro and "123456" not in registro and "ana@correo.co" not in registro


def test_armar_y_buzon_en_memoria() -> None:
    m = codigo_verificacion("ana@correo.co", "Ana", "123456", 15)
    correo = armar(m, "grupo@gmail.com")
    assert correo["From"] == "Nexabit <grupo@gmail.com>" and correo["Message-ID"].endswith("@gmail.com>")
    buzon = BuzonMemoria()
    buzon.enviar(m)
    assert buzon.ultimo() is m


@pytest.mark.parametrize(("error", "esperado"), [
    (smtplib.SMTPDataError(550, b"5.4.5 Daily user sending limit exceeded."), "límite diario"),
    (smtplib.SMTPDataError(550, b"5.7.1 Message rejected"), "respondió 550"),
    (smtplib.SMTPRecipientsRefused({"nadie@correo.co": (550, b"no existe")}), "rechazó la dirección"),
])
def test_errores_al_enviar_se_explican_sin_datos_personales(monkeypatch: pytest.MonkeyPatch,
                                                            caplog: pytest.LogCaptureFixture,
                                                            error: Exception, esperado: str) -> None:
    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
    monkeypatch.setattr(SmtpFalso, "error_envio", error)
    enviador = CorreoSmtp(DatosSmtp("smtp.gmail.com", 587, "g@gmail.com", "secreta", "g@gmail.com"))
    assert enviador.enviar_ahora(codigo_verificacion("nadie@correo.co", "Ana", "654321", 15)) is False
    assert esperado in caplog.text
    assert "nadie@correo.co" not in caplog.text and "654321" not in caplog.text


# ---------- Brevo (API por HTTPS): con un transporte falso, nunca se llama a Brevo ----------


def _brevo(estado: int, pedidos: list[httpx.Request]) -> CorreoBrevo:
    def responder(peticion: httpx.Request) -> httpx.Response:
        pedidos.append(peticion)
        return httpx.Response(estado, json={"messageId": "<1@brevo>"} if estado < 400 else {"code": "x"})

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    return CorreoBrevo(DatosBrevo("clave-secreta", "nexabit@correo.co"), cliente=cliente)


def test_brevo_desde_el_entorno_y_tiene_prioridad(tmp_path: Path) -> None:
    assert DatosBrevo.desde_entorno({}) is None
    assert DatosBrevo.desde_entorno({"BREVO_API_KEY": "k"}) is None  # falta el remitente
    datos = DatosBrevo.desde_entorno({"BREVO_API_KEY": " k ", "SMTP_USUARIO": "yo@gmail.com"})
    assert datos is not None and datos.remitente == "yo@gmail.com" and "k" not in repr(datos)
    entorno = {"BREVO_API_KEY": "k", "CORREO_REMITENTE": "otro@correo.co", "SMTP_USUARIO": "yo@gmail.com",
               "SMTP_CONTRASENA": "abcd efgh ijkl mnop"}
    enviador = enviador_desde_entorno(str(tmp_path), entorno)
    assert isinstance(enviador, CorreoBrevo) and "otro@correo.co" in enviador.descripcion()


def test_brevo_envia_el_correo_por_https() -> None:
    pedidos: list[httpx.Request] = []
    assert _brevo(201, pedidos).enviar_ahora(MensajeCorreo("ana@correo.co", "Tu código", "123456", "<b>123456</b>"))
    peticion = pedidos[0]
    assert str(peticion.url) == URL_BREVO and peticion.headers["api-key"] == "clave-secreta"
    cuerpo = json.loads(peticion.content)
    assert cuerpo["to"] == [{"email": "ana@correo.co"}] and cuerpo["sender"]["email"] == "nexabit@correo.co"
    assert cuerpo["htmlContent"] == "<b>123456</b>" and cuerpo["textContent"] == "123456"


@pytest.mark.parametrize(("estado", "fragmento"), [(401, "BREVO_API_KEY"), (429, "límite"), (400, "respondió 400")])
def test_brevo_errores_sin_datos_personales(estado: int, fragmento: str, caplog: pytest.LogCaptureFixture) -> None:
    pedidos: list[httpx.Request] = []
    with caplog.at_level("ERROR"):
        assert not _brevo(estado, pedidos).enviar_ahora(MensajeCorreo("ana@correo.co", "Código 123456", "t", "h"))
    assert fragmento in caplog.text
    assert "ana@correo.co" not in caplog.text and "123456" not in caplog.text and "clave-secreta" not in caplog.text


def test_brevo_sin_red_no_lanza(caplog: pytest.LogCaptureFixture) -> None:
    def falla(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    enviador = CorreoBrevo(DatosBrevo("k", "a@b.co"), cliente=httpx.Client(transport=httpx.MockTransport(falla)))
    with caplog.at_level("ERROR"):
        assert not enviador.enviar_ahora(MensajeCorreo("x@y.co", "a", "b", "c"))
    assert "ConnectError" in caplog.text
