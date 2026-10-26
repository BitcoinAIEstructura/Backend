"""Registro de actividad de seguridad de cada cuenta (para el "Centro de seguridad").

Queda constancia de inicios de sesión, intentos fallidos, cambios de contraseña y
de la verificación en dos pasos, así el usuario puede detectar accesos extraños.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from bitcoinai.basedatos import BaseDatos
from bitcoinai.estructuras import Lista


class TipoActividad(Enum):
    REGISTRO = "Cuenta creada"
    CORREO_VERIFICADO = "Correo confirmado"
    INICIO_SESION = "Inicio de sesión"
    INICIO_FALLIDO = "Intento de inicio de sesión fallido"
    CODIGO_FALLIDO = "Código de verificación incorrecto"
    CIERRE_SESION = "Cierre de sesión"
    SESIONES_CERRADAS = "Sesiones cerradas en otros dispositivos"
    CONTRASENA_CAMBIADA = "Contraseña cambiada"
    DOS_PASOS_ACTIVADA = "Verificación en dos pasos activada"
    DOS_PASOS_DESACTIVADA = "Verificación en dos pasos desactivada"
    CODIGO_RESPALDO_USADO = "Código de respaldo usado"
    CODIGOS_REGENERADOS = "Códigos de respaldo regenerados"


@dataclass(frozen=True, slots=True)
class EventoActividad:
    momento: int
    tipo: TipoActividad
    ip: str
    detalle: str


class RegistroActividad:
    def __init__(self, bd: BaseDatos, reloj: Callable[[], int] = lambda: int(time.time() * 1000)) -> None:
        self._bd = bd
        self._reloj = reloj

    def registrar(self, usuario_id: int, tipo: TipoActividad, ip: str, detalle: str = "") -> None:
        self._bd.ejecutar("INSERT INTO actividad (usuario_id, momento, tipo, ip, detalle) VALUES (?, ?, ?, ?, ?)",
                          (usuario_id, self._reloj(), tipo.name, ip, detalle[:300]))

    def recientes(self, usuario_id: int, limite: int = 50) -> Lista[EventoActividad]:
        """Los eventos más recientes primero."""
        resultado: Lista[EventoActividad] = Lista()
        for fila in self._bd.todas("SELECT * FROM actividad WHERE usuario_id = ? ORDER BY momento DESC, id DESC"
                                   " LIMIT ?", (usuario_id, limite)):
            resultado.agregar(EventoActividad(fila["momento"], TipoActividad[fila["tipo"]], fila["ip"],
                                              fila["detalle"]))
        return resultado
