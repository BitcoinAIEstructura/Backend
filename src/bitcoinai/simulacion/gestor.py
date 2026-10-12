"""Una simulación por usuario: su cartera, su libro de órdenes y su bot.

El gestor crea la simulación de cada usuario la primera vez que la necesita
(carga perezosa): arma su ``LibroDeOrdenes`` con la cola, las pilas y el registro
propios, la recupera del almacén y la deja en memoria para las siguientes
peticiones. No sabe de HTTP ni de SQL: recibe fábricas para el almacén y para el
publicador de cada usuario.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass

from bitcoinai.estrategia import Estrategia, EstrategiaCombinada
from bitcoinai.estructuras import Lista, TablaHash
from bitcoinai.mercado import FuenteDeMercado
from bitcoinai.simulacion.bot import BotSimulado, ConfiguracionBot, EstadoBot
from bitcoinai.simulacion.cartera import SALDO_INICIAL_POR_DEFECTO, Cartera
from bitcoinai.simulacion.interfaces import AlmacenSimulacion, PublicadorEventos, SinPublicar
from bitcoinai.simulacion.libro import LibroDeOrdenes
from bitcoinai.simulacion.modelo import OperacionInvalidaError

MAXIMO_BOTS_POR_DEFECTO = 20
"""Bots encendidos a la vez como máximo (cada uno consulta el mercado periódicamente)."""


@dataclass(frozen=True, slots=True)
class SimulacionUsuario:
    libro: LibroDeOrdenes
    bot: BotSimulado


class GestorSimulaciones:
    """Las simulaciones de todos los usuarios, en una tabla hash propia ``usuario_id → simulación``.

    Encontrar la simulación de quien hace la petición cuesta O(1) en promedio, sin
    importar cuántos usuarios haya cargados.
    """

    def __init__(self, fuente: FuenteDeMercado, simbolo: str,
                 crear_almacen: Callable[[int], AlmacenSimulacion] | None = None,
                 crear_publicador: Callable[[int], PublicadorEventos] | None = None,
                 crear_estrategia: Callable[[], Estrategia] = EstrategiaCombinada,
                 saldo_inicial: float = SALDO_INICIAL_POR_DEFECTO,
                 maximo_bots: int = MAXIMO_BOTS_POR_DEFECTO) -> None:
        self._fuente = fuente
        self._simbolo = simbolo
        self._crear_almacen = crear_almacen
        self._crear_publicador = crear_publicador or (lambda _usuario: SinPublicar())
        self._crear_estrategia = crear_estrategia
        self._saldo_inicial = saldo_inicial
        self.maximo_bots = maximo_bots
        self._simulaciones: TablaHash[int, SimulacionUsuario] = TablaHash()
        self._candado = threading.Lock()

    def _simulacion(self, usuario_id: int) -> SimulacionUsuario:
        """La simulación del usuario; la crea y la carga si es la primera vez. O(1) las siguientes."""
        with self._candado:
            existente = self._simulaciones.obtener(usuario_id)
            if existente is not None:
                return existente
            libro = LibroDeOrdenes(Cartera(self._saldo_inicial), self._fuente, self._simbolo)
            if self._crear_almacen is not None:
                libro.usar_almacen(self._crear_almacen(usuario_id))
            publicador = self._crear_publicador(usuario_id)
            libro.usar_publicador(publicador)
            # Cada bot con su propia estrategia: guardan memoria de indicadores entre ciclos.
            bot = BotSimulado(libro, self._fuente, self._crear_estrategia(), self._simbolo)
            bot.usar_publicador(publicador)
            nueva = SimulacionUsuario(libro, bot)
            self._simulaciones.poner(usuario_id, nueva)
            return nueva

    def libro(self, usuario_id: int) -> LibroDeOrdenes:
        return self._simulacion(usuario_id).libro

    def bot(self, usuario_id: int) -> BotSimulado:
        return self._simulacion(usuario_id).bot

    def cantidad_cargadas(self) -> int:
        with self._candado:
            return self._simulaciones.tamanio()

    def reparto_de_la_tabla(self) -> tuple[int, int, Lista[int]]:
        """Cubetas, simulaciones cargadas y cuántas hay en cada cubeta (sin ids: solo cantidades)."""
        with self._candado:
            return (self._simulaciones.capacidad(), self._simulaciones.tamanio(),
                    self._simulaciones.longitudes_de_cubetas())

    # ---------- bots ----------

    def bots_activos(self) -> int:
        """Cuántos bots están en marcha ahora. Complejidad: O(u) con u usuarios cargados."""
        with self._candado:
            return sum(1 for s in self._simulaciones.valores() if s.bot.estado().activo)

    def iniciar_bot(self, usuario_id: int, configuracion: ConfiguracionBot) -> EstadoBot:
        """Enciende el bot del usuario si no se llegó al máximo de bots a la vez.

        Raises:
            OperacionInvalidaError: si ya hay ``maximo_bots`` en marcha, o el suyo ya lo estaba.
        """
        bot = self.bot(usuario_id)
        with self._candado:
            activos = sum(1 for s in self._simulaciones.valores() if s.bot.estado().activo)
            if not bot.estado().activo and activos >= self.maximo_bots:
                raise OperacionInvalidaError(
                    f"Hay demasiados bots en marcha (máximo {self.maximo_bots}); intenta más tarde")
            return bot.iniciar(configuracion)

    def detener_todos(self) -> None:
        """Apaga todos los bots (al cerrar el servidor)."""
        with self._candado:
            simulaciones = tuple(self._simulaciones.valores())
        for simulacion in simulaciones:
            simulacion.bot.detener()
