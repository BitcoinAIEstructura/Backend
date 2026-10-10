"""Almacén de la simulación de un usuario en la base de datos.

Cumple la misma interfaz que ``AlmacenArchivos`` (``AlmacenSimulacion``), así el
libro de órdenes no sabe si guarda en archivos o en SQLite. Cada guardado
reemplaza la foto completa del usuario dentro de una transacción: o queda la
nueva entera o la anterior, nunca una mezcla.
"""

import logging
import time
from collections.abc import Callable

from bitcoinai.basedatos import BaseDatos, Fila
from bitcoinai.estructuras import Lista
from bitcoinai.simulacion import (
    DatosCartera,
    EstadoOrden,
    EstadoSimulacion,
    Evento,
    Orden,
    TipoEvento,
    TipoOrden,
)

LOG = logging.getLogger("bitcoinai.persistencia")


def _ahora_ms() -> int:
    return int(time.time() * 1000)


def _fila_orden(usuario_id: int, lugar: str, posicion: int, o: Orden) -> tuple[object, ...]:
    return (usuario_id, o.id, lugar, posicion, o.tipo.name, o.monto, int(o.todo), o.estado.name, o.creada_en,
            o.ejecutada_en, o.precio_ejecucion, o.cantidad_btc, o.comision, o.motivo, o.detalle)


def _orden(f: Fila) -> Orden:
    return Orden(f["id"], TipoOrden[f["tipo"]], f["monto"], bool(f["todo"]), EstadoOrden[f["estado"]], f["creada_en"],
                 f["ejecutada_en"], f["precio_ejecucion"], f["cantidad_btc"], f["comision"], f["motivo"], f["detalle"])


class AlmacenBaseDatos:
    """Guarda y carga la simulación de ``usuario_id``."""

    def __init__(self, bd: BaseDatos, usuario_id: int, reloj: Callable[[], int] = _ahora_ms) -> None:
        self._bd = bd
        self.usuario_id = usuario_id
        self._reloj = reloj

    def guardar(self, estado: EstadoSimulacion) -> None:
        """Reemplaza la foto del usuario. Complejidad: O(n) en el tamaño del estado."""
        u = self.usuario_id
        c = estado.cartera
        with self._bd.transaccion():
            if c is not None:
                self._bd.ejecutar(
                    "INSERT INTO simulaciones (usuario_id, saldo_inicial, saldo_usdt, btc, costo_posicion,"
                    " ganancia_realizada, comisiones_pagadas, siguiente_id, actualizado_en)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT (usuario_id) DO UPDATE SET saldo_inicial = excluded.saldo_inicial,"
                    " saldo_usdt = excluded.saldo_usdt, btc = excluded.btc, costo_posicion = excluded.costo_posicion,"
                    " ganancia_realizada = excluded.ganancia_realizada,"
                    " comisiones_pagadas = excluded.comisiones_pagadas, siguiente_id = excluded.siguiente_id,"
                    " actualizado_en = excluded.actualizado_en",
                    (u, c.saldo_inicial, c.saldo_usdt, c.btc, c.costo_posicion, c.ganancia_realizada,
                     c.comisiones_pagadas, estado.siguiente_id, self._reloj()))
            for tabla in ("ordenes", "ordenes_creadas", "eventos_simulacion"):
                self._bd.ejecutar(f"DELETE FROM {tabla} WHERE usuario_id = ?", (u,))  # nombre fijo, no del usuario
            columnas = ("usuario_id, id, lugar, posicion, tipo, monto, todo, estado, creada_en, ejecutada_en,"
                        " precio_ejecucion, cantidad_btc, comision, motivo, detalle")
            insertar_orden = f"INSERT INTO ordenes ({columnas}) VALUES ({', '.join('?' * 15)})"
            self._bd.ejecutar_muchos(insertar_orden, (_fila_orden(u, "pendiente", i, o)
                                                      for i, o in enumerate(estado.pendientes)))
            self._bd.ejecutar_muchos(insertar_orden, (_fila_orden(u, "registro", i, o)
                                                      for i, o in enumerate(estado.registro)))
            self._bd.ejecutar_muchos("INSERT INTO ordenes_creadas (usuario_id, posicion, id_orden) VALUES (?, ?, ?)",
                                     ((u, i, id_orden) for i, id_orden in enumerate(estado.creadas)))
            self._bd.ejecutar_muchos(
                "INSERT INTO eventos_simulacion (usuario_id, posicion, momento, tipo, id_orden, descripcion)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                ((u, i, e.momento, e.tipo.name, e.id_orden, e.descripcion) for i, e in enumerate(estado.eventos)))

    def cargar(self) -> EstadoSimulacion | None:
        """La última foto guardada, o None si el usuario todavía no tiene simulación.

        Nunca falla: si los datos guardados son inválidos, lo registra y empieza limpio.
        """
        u = self.usuario_id
        fila = self._bd.una("SELECT * FROM simulaciones WHERE usuario_id = ?", (u,))
        if fila is None:
            return None
        try:
            cartera = DatosCartera(fila["saldo_inicial"], fila["saldo_usdt"], fila["btc"], fila["costo_posicion"],
                                   fila["ganancia_realizada"], fila["comisiones_pagadas"])
            pendientes: Lista[Orden] = Lista()
            registro: Lista[Orden] = Lista()
            for f in self._bd.todas("SELECT * FROM ordenes WHERE usuario_id = ? ORDER BY lugar, posicion", (u,)):
                (pendientes if f["lugar"] == "pendiente" else registro).agregar(_orden(f))
            creadas: Lista[int] = Lista()
            for f in self._bd.todas("SELECT id_orden FROM ordenes_creadas WHERE usuario_id = ? ORDER BY posicion",
                                    (u,)):
                creadas.agregar(int(f["id_orden"]))
            eventos: Lista[Evento] = Lista()
            for f in self._bd.todas("SELECT * FROM eventos_simulacion WHERE usuario_id = ? ORDER BY posicion", (u,)):
                eventos.agregar(Evento(f["momento"], TipoEvento[f["tipo"]], f["id_orden"], f["descripcion"]))
        except (KeyError, ValueError) as error:
            LOG.warning("Simulación guardada del usuario %d inutilizable (%s); se empieza limpia.", u, error)
            return None
        return EstadoSimulacion(cartera, int(fila["siguiente_id"]), pendientes, registro, creadas, eventos)
