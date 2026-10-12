"""¿Y si hubiera invertido? Cuánto valdría hoy una compra hecha en una fecha del pasado.

Las velas se indexan en un árbol AVL por su hora de apertura:

- ``techo(fecha)`` encuentra la primera vela de ese día (o la siguiente con datos)
  en O(log n), sin recorrer las anteriores.
- ``rango(fecha, hoy)`` recorre solo las velas desde ese día, en orden, para hallar
  el mejor y el peor momento para haber vendido: O(log n + k).

Es un cálculo hipotético con datos reales del mercado: no es una predicción.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from bitcoinai.estructuras import ArbolAVL
from bitcoinai.modelo import Vela
from bitcoinai.simulacion.libro import COMISION_POR_DEFECTO


class FechaSinDatosError(ValueError):
    """La fecha pedida está antes de la primera vela o después de la última."""


@dataclass(frozen=True, slots=True)
class Momento:
    tiempo: int
    precio: float


@dataclass(frozen=True, slots=True)
class ResultadoSiHubiera:
    """Qué habría pasado. Los montos en USDT; ``btc`` ya descuenta la comisión de compra."""

    vela: Vela
    monto: float
    btc: float
    precio_actual: float
    valor_hoy: float
    ganancia: float
    rentabilidad: float
    mejor: Momento
    peor: Momento
    velas_recorridas: int


class IndiceVelas:
    """Velas indexadas por su hora de apertura en un ``ArbolAVL``."""

    def __init__(self, velas: Iterable[Vela]) -> None:
        """Arma el índice. O(n log n); el AVL no se desbalancea aunque lleguen ordenadas."""
        self._arbol: ArbolAVL[int, Vela] = ArbolAVL()
        for vela in velas:
            self._arbol.insertar(vela.tiempo_apertura, vela)

    @property
    def arbol(self) -> ArbolAVL[int, Vela]:
        return self._arbol

    def desde(self) -> int:
        """Apertura de la primera vela. O(log n)."""
        return self._arbol.minimo()[0]

    def hasta(self) -> int:
        """Apertura de la última vela. O(log n)."""
        return self._arbol.maximo()[0]

    def si_hubiera(self, fecha_ms: int, monto: float, precio_actual: float,
                   comision: float = COMISION_POR_DEFECTO) -> ResultadoSiHubiera:
        """Compra de ``monto`` USDT al abrir la primera vela desde ``fecha_ms``, valorada hoy.

        Raises:
            FechaSinDatosError: si no hay velas para esa fecha.
        """
        if self._arbol.esta_vacio():
            raise FechaSinDatosError("No hay velas para calcular")
        if fecha_ms < self.desde():
            raise FechaSinDatosError("Esa fecha es anterior a los datos disponibles")
        encontrada = self._arbol.techo(fecha_ms)
        if encontrada is None:
            raise FechaSinDatosError("Todavía no hay datos de esa fecha")
        _, vela = encontrada
        btc = monto * (1 - comision) / vela.apertura
        valor_hoy = btc * precio_actual
        mejor = peor = Momento(vela.tiempo_apertura, vela.apertura)
        recorridas = 0
        for tiempo, v in self._arbol.rango(vela.tiempo_apertura, self.hasta()):
            recorridas += 1
            if v.maximo > mejor.precio:
                mejor = Momento(tiempo, v.maximo)
            if v.minimo < peor.precio:
                peor = Momento(tiempo, v.minimo)
        return ResultadoSiHubiera(vela, monto, btc, precio_actual, valor_hoy, valor_hoy - monto,
                                  (valor_hoy - monto) / monto, mejor, peor, recorridas)
