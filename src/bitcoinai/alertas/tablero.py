"""Alertas de precio en dos montículos: se revisan solo los topes en cada precio nuevo."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum

from bitcoinai.estructuras import Lista, Monticulo, TablaHash


class TipoAlerta(Enum):
    SUBE_A = "SUBE_A"  # avisar cuando el precio llegue o pase hacia arriba
    BAJA_A = "BAJA_A"  # avisar cuando el precio llegue o pase hacia abajo


class EstadoAlerta(Enum):
    ACTIVA = "ACTIVA"
    DISPARADA = "DISPARADA"
    CANCELADA = "CANCELADA"


@dataclass(frozen=True, slots=True)
class Alerta:
    id: int
    usuario_id: int
    tipo: TipoAlerta
    precio: float
    estado: EstadoAlerta
    creada_en: int
    disparada_en: int | None = None
    precio_disparo: float | None = None

    def disparada(self, momento: int, precio: float) -> "Alerta":
        return replace(self, estado=EstadoAlerta.DISPARADA, disparada_en=momento, precio_disparo=precio)


class TableroAlertas:
    """Las alertas activas de todos los usuarios.

    - ``SUBE_A`` va a un montículo de **mínimos** por precio: la más baja es la
      primera que se cumple cuando el precio sube.
    - ``BAJA_A`` va a un montículo de **máximos**: la más alta es la primera que se
      cumple cuando el precio baja.

    Con cada precio nuevo se miran solo los topes y se sacan mientras se cumplan:
    O(k log n) con k disparadas, sin recorrer las n alertas.

    Cancelar es perezoso: la alerta queda marcada en una ``TablaHash`` y se descarta
    cuando llega al tope (sacarla del medio de un montículo costaría O(n)).
    """

    def __init__(self) -> None:
        self._suben: Monticulo[Alerta] = Monticulo(lambda a: a.precio)
        self._bajan: Monticulo[Alerta] = Monticulo(lambda a: a.precio, mayor_primero=True)
        self._activas: TablaHash[int, Alerta] = TablaHash()

    def agregar(self, alerta: Alerta) -> None:
        """O(log n)."""
        self._activas.poner(alerta.id, alerta)
        (self._suben if alerta.tipo is TipoAlerta.SUBE_A else self._bajan).insertar(alerta)

    def cancelar(self, id_alerta: int) -> bool:
        """O(1): se olvida de ella; el montículo la descarta cuando salga. True si estaba activa."""
        return self._activas.eliminar(id_alerta)

    def revisar(self, precio: float, momento: int) -> Lista[Alerta]:
        """Las alertas que se cumplen con este precio, ya marcadas como disparadas. O(k log n)."""
        disparadas: Lista[Alerta] = Lista()
        self._sacar(self._suben, lambda a: precio >= a.precio, disparadas, momento, precio)
        self._sacar(self._bajan, lambda a: precio <= a.precio, disparadas, momento, precio)
        return disparadas

    def _sacar(self, monticulo: Monticulo[Alerta], se_cumple: Callable[[Alerta], bool],
               disparadas: Lista[Alerta], momento: int, precio: float) -> None:
        """Saca del tope mientras se cumpla, descartando las canceladas que aparezcan."""
        while not monticulo.esta_vacia():
            tope = monticulo.ver_tope()
            if not self._activas.contiene(tope.id):
                monticulo.extraer()  # cancelada: se descarta ahora
                continue
            if not se_cumple(tope):
                return
            monticulo.extraer()
            self._activas.eliminar(tope.id)
            disparadas.agregar(tope.disparada(momento, precio))

    def activas_de(self, usuario_id: int) -> int:
        """Cuántas activas tiene un usuario. O(n)."""
        return sum(1 for a in self._activas.valores() if a.usuario_id == usuario_id)

    def tamanio(self) -> int:
        """Alertas activas en total. O(1)."""
        return self._activas.tamanio()

    def proximas(self) -> tuple[float | None, float | None]:
        """El precio más bajo que hace disparar una subida y el más alto de una bajada (para mostrar)."""
        def tope(m: Monticulo[Alerta]) -> float | None:
            while not m.esta_vacia() and not self._activas.contiene(m.ver_tope().id):
                m.extraer()
            return None if m.esta_vacia() else m.ver_tope().precio
        return tope(self._suben), tope(self._bajan)
