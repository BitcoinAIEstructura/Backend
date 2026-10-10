"""Conversión entre los objetos de la simulación y el JSON guardado en disco.

Al leer se valida cada campo: cualquier dato faltante o del tipo equivocado lanza
``DatosDanadosError``. Las claves son las mismas que usa la API (camelCase), así un
archivo guardado se lee igual que una respuesta. Cada conversión es O(tamaño del dato).
"""

import math
from enum import Enum
from typing import Any

from bitcoinai.simulacion import DatosCartera, EstadoOrden, Evento, Orden, TipoEvento, TipoOrden


class DatosDanadosError(Exception):
    """Un archivo guardado no tiene el formato esperado."""


# ---------- a JSON ----------


def cartera_a_json(datos: DatosCartera) -> dict[str, Any]:
    return {
        "saldoInicial": datos.saldo_inicial,
        "saldoUsdt": datos.saldo_usdt,
        "btc": datos.btc,
        "costoPosicion": datos.costo_posicion,
        "gananciaRealizada": datos.ganancia_realizada,
        "comisionesPagadas": datos.comisiones_pagadas,
    }


def orden_a_json(orden: Orden) -> dict[str, Any]:
    return {
        "id": orden.id,
        "tipo": orden.tipo.name,
        "monto": orden.monto,
        "todo": orden.todo,
        "estado": orden.estado.name,
        "creadaEn": orden.creada_en,
        "ejecutadaEn": orden.ejecutada_en,
        "precioEjecucion": orden.precio_ejecucion,
        "cantidadBtc": orden.cantidad_btc,
        "comision": orden.comision,
        "motivo": orden.motivo,
        "detalle": orden.detalle,
    }


def evento_a_json(evento: Evento) -> dict[str, Any]:
    return {
        "momento": evento.momento,
        "tipo": evento.tipo.name,
        "idOrden": evento.id_orden,
        "descripcion": evento.descripcion,
    }


# ---------- desde JSON ----------


def cartera(valor: object) -> DatosCartera:
    m = mapa(valor, "cartera")
    try:
        return DatosCartera(numero(m, "saldoInicial"), numero(m, "saldoUsdt"), numero(m, "btc"),
                            numero(m, "costoPosicion"), numero(m, "gananciaRealizada"),
                            numero(m, "comisionesPagadas"))
    except ValueError as error:
        raise DatosDanadosError(f"cartera con valores imposibles: {error}") from error


def orden(valor: object) -> Orden:
    m = mapa(valor, "orden")
    id_orden = entero(m, "id")
    tipo = enumerado(m, "tipo", TipoOrden)
    todo = booleano(m, "todo")
    monto = numero_opcional(m, "monto")
    if id_orden < 1 or (todo and tipo is not TipoOrden.VENTA) or (not todo and monto is None):
        raise DatosDanadosError(f"orden #{id_orden} con datos incoherentes")
    return Orden(id_orden, tipo, monto, todo, enumerado(m, "estado", EstadoOrden), entero(m, "creadaEn"),
                 entero_opcional(m, "ejecutadaEn"), numero_opcional(m, "precioEjecucion"),
                 numero_opcional(m, "cantidadBtc"), numero_opcional(m, "comision"), texto(m, "motivo"),
                 texto_opcional(m, "detalle"))


def evento(valor: object) -> Evento:
    m = mapa(valor, "evento")
    return Evento(entero(m, "momento"), enumerado(m, "tipo", TipoEvento), entero_opcional(m, "idOrden"),
                  texto(m, "descripcion"))


# ---------- utilidades ----------


def mapa(valor: object, que: str) -> dict[str, Any]:
    if not isinstance(valor, dict):
        raise DatosDanadosError(f"se esperaba un objeto en {que}")
    return valor


def lista(m: dict[str, Any], campo: str) -> list[Any]:
    """La lista tal como la devuelve ``json`` (frontera JSON); se recorre una vez para pasarla a Lista."""
    valor = m.get(campo)
    if not isinstance(valor, list):
        raise DatosDanadosError(f"falta la lista '{campo}'")
    return valor


def numero_opcional(m: dict[str, Any], campo: str) -> float | None:
    valor = m.get(campo)
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int | float) or not math.isfinite(valor):
        raise DatosDanadosError(f"el campo '{campo}' debe ser un número")
    return float(valor)


def numero(m: dict[str, Any], campo: str) -> float:
    valor = numero_opcional(m, campo)
    if valor is None:
        raise DatosDanadosError(f"falta el número '{campo}'")
    return valor


def entero_opcional(m: dict[str, Any], campo: str) -> int | None:
    valor = numero_opcional(m, campo)
    if valor is None:
        return None
    if valor != math.floor(valor):
        raise DatosDanadosError(f"el campo '{campo}' debe ser un entero")
    return int(valor)


def entero(m: dict[str, Any], campo: str) -> int:
    valor = entero_opcional(m, campo)
    if valor is None:
        raise DatosDanadosError(f"falta el entero '{campo}'")
    return valor


def texto_opcional(m: dict[str, Any], campo: str) -> str | None:
    valor = m.get(campo)
    if valor is not None and not isinstance(valor, str):
        raise DatosDanadosError(f"el campo '{campo}' debe ser un texto")
    return valor


def texto(m: dict[str, Any], campo: str) -> str:
    valor = texto_opcional(m, campo)
    if valor is None:
        raise DatosDanadosError(f"falta el texto '{campo}'")
    return valor


def booleano(m: dict[str, Any], campo: str) -> bool:
    valor = m.get(campo)
    if not isinstance(valor, bool):
        raise DatosDanadosError(f"el campo '{campo}' debe ser true o false")
    return valor


def enumerado[E: Enum](m: dict[str, Any], campo: str, tipo: type[E]) -> E:
    nombre = texto(m, campo)
    try:
        return tipo[nombre]
    except KeyError:
        raise DatosDanadosError(f"valor desconocido en '{campo}': {nombre}") from None
