"""Interfaces que separan la simulación del tiempo real (HTTP) y de la persistencia (archivos)."""

import math
from dataclasses import dataclass
from typing import Protocol

from bitcoinai.estructuras import Lista
from bitcoinai.simulacion.modelo import Evento, Orden


class PublicadorEventos(Protocol):
    """Destino de los eventos en tiempo real ("orden", "cartera", "senal").

    El libro de órdenes y el bot solo conocen esta interfaz; quien la implementa
    (el ``api.Publicador`` con SSE) vive en la capa HTTP. Así la simulación no
    depende de HTTP y en las pruebas se puede reemplazar. Las implementaciones no
    deben bloquear: se llama con candados tomados.
    """

    def publicar(self, tipo: str, datos: object) -> None:
        """Publica un evento (los datos son objetos del dominio)."""
        ...


class SinPublicar:
    """Publicador que descarta todo, para cuando no hay tiempo real."""

    def publicar(self, tipo: str, datos: object) -> None:
        return


@dataclass(frozen=True, slots=True)
class DatosCartera:
    """Datos mínimos para reconstruir una Cartera (lo que se guarda en disco)."""

    saldo_inicial: float
    saldo_usdt: float
    btc: float
    costo_posicion: float
    ganancia_realizada: float
    comisiones_pagadas: float

    def __post_init__(self) -> None:
        """Raises: ValueError si algún valor es imposible (negativo o no finito)."""
        no_negativos = (self.saldo_usdt, self.btc, self.costo_posicion, self.comisiones_pagadas)
        if not (self.saldo_inicial > 0 and math.isfinite(self.saldo_inicial)):
            raise ValueError("Datos de cartera imposibles: el saldo inicial debe ser positivo")
        if not all(v >= 0 and math.isfinite(v) for v in no_negativos) or not math.isfinite(self.ganancia_realizada):
            raise ValueError("Datos de cartera imposibles: hay valores negativos o no finitos")


@dataclass(frozen=True, slots=True)
class EstadoSimulacion:
    """Foto completa del libro de órdenes, para guardarla y reconstruirla.

    Las listas van en el orden en que hay que volver a cargarlas:
    ``pendientes`` en orden de cola (la primera es el frente); ``registro`` en el
    orden en que terminaron; ``creadas`` y ``eventos`` del más viejo al más nuevo
    (el último es el tope de la pila). ``cartera`` es None si no había.
    """

    cartera: DatosCartera | None
    siguiente_id: int
    pendientes: Lista[Orden]
    registro: Lista[Orden]
    creadas: Lista[int]
    eventos: Lista[Evento]


class AlmacenSimulacion(Protocol):
    """Dónde se guarda el estado de la simulación (la implementación está en ``persistencia``)."""

    def guardar(self, estado: EstadoSimulacion) -> None:
        """Guarda el estado completo. Si falla, lanza; el libro lo registra y sigue."""
        ...

    def cargar(self) -> EstadoSimulacion | None:
        """Último estado guardado, o None si no hay nada utilizable (nunca falla)."""
        ...
