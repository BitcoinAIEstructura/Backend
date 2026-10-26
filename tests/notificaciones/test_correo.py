import smtplib
from email import message_from_bytes, policy
from pathlib import Path
from typing import Any

import pytest

from bitcoinai.notificaciones import BuzonLocal, BuzonMemoria, CorreoSmtp, DatosSmtp, enviador_desde_entorno
from bitcoinai.notificaciones.correo import armar
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


def test_con_smtp_usa_gmail(tmp_path: Path) -> None:
    enviador = enviador_desde_entorno(str(tmp_path), {"SMTP_USUARIO": "g@gmail.com", "SMTP_CONTRASENA": "x"})
    assert isinstance(enviador, CorreoSmtp) and "smtp.gmail.com:587" in enviador.descripcion()


class SmtpFalso:
    """Imita smtplib.SMTP y anota lo que se hizo."""

    hechos: list[str] = []
    falla_login = False

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
        SmtpFalso.hechos.append(f"enviar a {mensaje['To']}")


def test_smtp_con_starttls_y_errores_sin_lanzar(monkeypatch: pytest.MonkeyPatch,
                                                caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
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
    assert "contraseña de aplicación" in registro
    assert "secreta" not in registro and "123456" not in registro and "ana@correo.co" not in registro


def test_armar_y_buzon_en_memoria() -> None:
    m = codigo_verificacion("ana@correo.co", "Ana", "123456", 15)
    correo = armar(m, "grupo@gmail.com")
    assert correo["From"] == "Nexabit <grupo@gmail.com>" and correo["Message-ID"].endswith("@gmail.com>")
    buzon = BuzonMemoria()
    buzon.enviar(m)
    assert buzon.ultimo() is m
