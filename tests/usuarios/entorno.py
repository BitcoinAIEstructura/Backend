"""Servicio de cuentas listo para las pruebas: base en memoria, hash rápido y relojes controlables."""

from dataclasses import dataclass

from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.seguridad.contrasenas import PARAMETROS_RAPIDOS_PARA_PRUEBAS, HashContrasenas
from bitcoinai.usuarios.modelo import DatosRegistro
from bitcoinai.usuarios.servicio import Cliente, ServicioCuentas

CONTRASENA = "Luna-Roja-2026"
CLIENTE = Cliente("127.0.0.1", "Pruebas/1.0")


class Reloj:
    """Reloj manual: ``ahora`` en segundos; ``ms()`` en milisegundos."""

    def __init__(self) -> None:
        self.ahora = 1_800_000_000.0

    def __call__(self) -> float:
        return self.ahora

    def ms(self) -> int:
        return int(self.ahora * 1000)


@dataclass
class Entorno:
    servicio: ServicioCuentas
    reloj: Reloj
    bd: BaseDatos


def crear_entorno() -> Entorno:
    bd = BaseDatos(":memory:")
    migrar(bd)
    reloj = Reloj()
    servicio = ServicioCuentas(bd, Cifrador(bytes(32)), HashContrasenas(PARAMETROS_RAPIDOS_PARA_PRUEBAS),
                               reloj_ms=reloj.ms, reloj_s=reloj)
    return Entorno(servicio, reloj, bd)


def datos(correo: str = "ana@correo.co", documento: str = "1023456789") -> DatosRegistro:
    return DatosRegistro.validar("Ana", "Pérez", correo, "CC", documento, "3001234567", CONTRASENA)
