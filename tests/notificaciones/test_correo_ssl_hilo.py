"""El envío por SMTP en los casos que faltaban: TLS directo, el hilo y una caída de red.

- Puerto 465: se conecta con ``SMTP_SSL`` (TLS desde el primer byte), no con STARTTLS.
- ``enviar`` no bloquea la petición: lanza el envío en un hilo aparte.
- Un ``OSError`` (sin red, DNS caído) se registra por su tipo, sin datos personales.
"""

import logging
import smtplib
from typing import Any

import pytest

from bitcoinai.notificaciones import BuzonMemoria, CorreoSmtp, DatosSmtp
from bitcoinai.notificaciones import correo as modulo_correo
from bitcoinai.notificaciones.plantillas import codigo_verificacion


class SmtpSslFalso:
    """Imita smtplib.SMTP_SSL y anota lo que se hizo y con qué contexto de TLS."""

    hechos: list[str] = []
    contextos: list[Any] = []

    def __init__(self, host: str, puerto: int, timeout: float, context: Any = None) -> None:
        SmtpSslFalso.hechos.append(f"ssl {host}:{puerto}")
        SmtpSslFalso.contextos.append(context)

    def __enter__(self) -> "SmtpSslFalso":
        return self

    def __exit__(self, *_: Any) -> None:
        SmtpSslFalso.hechos.append("cerrar")

    def login(self, usuario: str, contrasena: str) -> None:
        SmtpSslFalso.hechos.append(f"login {usuario}")

    def send_message(self, mensaje: Any) -> None:
        SmtpSslFalso.hechos.append(f"enviar a {mensaje['To']}")

    def starttls(self, context: Any) -> None:  # pragma: no cover - no debe llamarse nunca
        raise AssertionError("en el puerto 465 no se usa STARTTLS")


def test_puerto_465_usa_tls_directo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpSslFalso)
    SmtpSslFalso.hechos, SmtpSslFalso.contextos = [], []
    enviador = CorreoSmtp(DatosSmtp("smtp.gmail.com", 465, "g@gmail.com", "secreta", "g@gmail.com"))
    mensaje = codigo_verificacion("ana@correo.co", "Ana", "123456", 15)

    assert enviador.enviar_ahora(mensaje) is True
    assert SmtpSslFalso.hechos == ["ssl smtp.gmail.com:465", "login g@gmail.com",
                                   "enviar a ana@correo.co", "cerrar"]
    assert SmtpSslFalso.contextos[0] is not None  # contexto TLS por defecto del sistema


def test_enviar_no_bloquea_y_usa_un_hilo(monkeypatch: pytest.MonkeyPatch) -> None:
    creados: list[dict[str, Any]] = []

    class HiloFalso:
        def __init__(self, target: Any, args: tuple[Any, ...], name: str, daemon: bool) -> None:
            creados.append({"target": target, "args": args, "name": name, "daemon": daemon})

        def start(self) -> None:
            registro = creados[-1]
            registro["target"](*registro["args"])

    monkeypatch.setattr(modulo_correo.threading, "Thread", HiloFalso)
    enviador = CorreoSmtp(DatosSmtp("smtp.gmail.com", 587, "g@gmail.com", "secreta", "g@gmail.com"))
    enviados: list[Any] = []
    enviador.enviar_ahora = enviados.append  # type: ignore[method-assign]
    mensaje = codigo_verificacion("ana@correo.co", "Ana", "123456", 15)

    enviador.enviar(mensaje)

    assert enviados == [mensaje]
    assert creados == [{"target": enviador.enviar_ahora, "args": (mensaje,), "name": "correo", "daemon": True}]


def test_una_caida_de_red_no_lanza_y_se_registra_por_su_tipo(
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    class SmtpSinRed:
        def __init__(self, *_: Any, **__: Any) -> None:
            raise OSError("Network is unreachable")

    monkeypatch.setattr(smtplib, "SMTP", SmtpSinRed)
    enviador = CorreoSmtp(DatosSmtp("smtp.gmail.com", 587, "g@gmail.com", "secreta", "g@gmail.com"))
    caplog.set_level(logging.ERROR)

    assert enviador.enviar_ahora(codigo_verificacion("ana@correo.co", "Ana", "123456", 15)) is False
    assert "No se pudo enviar un correo: OSError" in caplog.text
    assert "ana@correo.co" not in caplog.text and "123456" not in caplog.text


def test_el_buzon_en_memoria_se_describe_así() -> None:
    assert BuzonMemoria().descripcion() == "en memoria"
