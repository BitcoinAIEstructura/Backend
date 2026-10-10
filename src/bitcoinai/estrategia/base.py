"""Clase base de las estrategias, con memoria incremental."""

import threading
from abc import ABC, abstractmethod

from bitcoinai.estrategia import apoyo
from bitcoinai.estrategia.modelo import Decision
from bitcoinai.estructuras import Lista, ListaDoble
from bitcoinai.modelo import Vela


class Estrategia(ABC):
    """Estrategia de trading: mira las velas hasta ahora y decide comprar, vender o mantener.

    Regla de oro: ``evaluar`` solo puede usar las velas que recibe. Así el
    backtest garantiza que nunca se mira el futuro.

    **Memoria incremental.** Recalcular los indicadores desde la primera vela en
    cada paso del backtest costaría O(n) por vela, O(n²) en total. Por eso cada
    estrategia recuerda el estado de sus indicadores para la última lista que
    vio. Si recibe *la misma lista con una vela más al final* (lo que hace el
    backtest), solo procesa esa vela: O(1). Si recibe otra lista, o la misma
    modificada de otra forma, recalcula todo desde cero: O(n). Lo que recuerda
    sale solo de velas ya recibidas, así que no mira el futuro. Para detectar la
    continuación se comparan en O(1) la primera vela y la penúltima (``obtener``
    de la ListaDoble llega desde el extremo más cercano).

    Las subclases implementan ``_reiniciar`` (estado vacío), ``_agregar`` (procesa
    una vela), ``_decidir`` (decide con el estado actual) y ``_valores_actuales``.
    """

    def __init__(self) -> None:
        self._candado = threading.RLock()
        self._lista: ListaDoble[Vela] | None = None
        self._procesadas = 0
        self._primera: Vela | None = None
        self._ultima: Vela | None = None
        self._reiniciar()

    # ---------- lo que define cada estrategia ----------

    @abstractmethod
    def nombre(self) -> str:
        """Nombre corto, por ejemplo ``"cruce"``."""

    @abstractmethod
    def parametros(self) -> dict[str, object]:
        """Parámetros con que se creó."""

    @abstractmethod
    def velas_minimas(self) -> int:
        """Cuántas velas necesita como mínimo para poder dar una señal."""

    @abstractmethod
    def _decidir(self, velas: ListaDoble[Vela]) -> Decision:
        """Decide con el estado actual (ya sincronizado y con velas suficientes)."""

    def _reiniciar(self) -> None:
        """Deja el estado de los indicadores vacío. Por defecto no hay estado."""
        return

    def _agregar(self, vela: Vela) -> None:
        """Procesa una vela nueva en O(1). Por defecto no hace nada."""
        return

    def _valores_actuales(self) -> dict[str, float]:
        """Último valor de cada indicador con el estado actual."""
        return {}

    # ---------- interfaz pública ----------

    def evaluar(self, velas_hasta_ahora: ListaDoble[Vela] | None) -> Decision:
        """Decide qué hacer en la última vela recibida.

        Con menos de ``velas_minimas()`` velas devuelve MANTENER con confianza 0.
        Las velas no se modifican.
        Complejidad: O(1) si es la lista anterior con una vela más; O(n) si no.
        """
        if velas_hasta_ahora is None or velas_hasta_ahora.esta_vacia():
            return apoyo.faltan_velas(velas_hasta_ahora, self.velas_minimas())
        with self._candado:
            self._sincronizar(velas_hasta_ahora)
            if velas_hasta_ahora.tamanio() < self.velas_minimas():
                return apoyo.faltan_velas(velas_hasta_ahora, self.velas_minimas())
            return self._decidir(velas_hasta_ahora)

    def indicadores_actuales(self, velas: ListaDoble[Vela]) -> dict[str, float]:
        """Último valor de los indicadores que usa, para explicar la decisión (vacío si faltan datos)."""
        if velas.esta_vacia():
            return {}
        with self._candado:
            self._sincronizar(velas)
            return self._valores_actuales()

    def justificacion(self, velas: ListaDoble[Vela], decision: Decision) -> Lista[str]:
        """Frases que justifican una decisión. Por defecto, su motivo."""
        frases: Lista[str] = Lista()
        frases.agregar(decision.motivo)
        return frases

    # ---------- memoria incremental ----------

    def _sincronizar(self, velas: ListaDoble[Vela]) -> None:
        """Pone el estado al día con ``velas``: O(1) si solo llegó una vela nueva al final."""
        n = velas.tamanio()
        misma = velas is self._lista and velas.primero() is self._primera
        if misma and n == self._procesadas and velas.ultimo() is self._ultima:
            return  # nada nuevo
        if misma and n == self._procesadas + 1 and velas.obtener(n - 2) is self._ultima:
            self._agregar(velas.ultimo())
        else:
            self._reiniciar()
            for vela in velas:
                self._agregar(vela)
        self._lista = velas
        self._procesadas = n
        self._primera = velas.primero()
        self._ultima = velas.ultimo()
