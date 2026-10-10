"""Persistencia de la simulación: en archivos JSON (un solo usuario) o en la base de datos (por usuario)."""

from bitcoinai.persistencia.almacen import CARTERA, HISTORIAL, ORDENES, AlmacenArchivos
from bitcoinai.persistencia.almacen_bd import AlmacenBaseDatos
from bitcoinai.persistencia.conversor import DatosDanadosError

__all__ = ("CARTERA", "HISTORIAL", "ORDENES", "AlmacenArchivos", "AlmacenBaseDatos", "DatosDanadosError")
