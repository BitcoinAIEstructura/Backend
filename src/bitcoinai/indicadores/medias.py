"""Medias móviles: SMA y EMA."""

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import series
from bitcoinai.indicadores.base import Indicador, PuntoIndicador, Serie
from bitcoinai.modelo import Vela


class Sma(Indicador):
    """Media móvil simple (SMA) de los cierres.

    Fórmula: SMAₜ = (xₜ + xₜ₋₁ + … + xₜ₋ₚ₊₁) / p.

    Mantiene una ventana (``ListaDoble``) con los últimos p cierres y su suma
    acumulada: al entrar un cierre se suma, y cuando la ventana pasa de p se resta
    el más antiguo y se recorta con ``conservar_ultimos(p)``. Así cada vela cuesta
    O(1) y el total es O(n), en vez de O(n·p) si se sumara la ventana completa en
    cada vela. Memoria extra: O(p).
    """

    def __init__(self, periodo: int) -> None:
        """Raises: ValueError si el periodo es menor que 1."""
        self.periodo = series.validar_periodo(periodo)

    def nombre(self) -> str:
        return "sma"

    def parametros(self) -> dict[str, object]:
        return {"periodo": self.periodo}

    def calcular(self, velas: ListaDoble[Vela] | None) -> Serie:
        """Complejidad: O(n) en tiempo, O(p) en memoria extra."""
        resultado: Serie = ListaDoble()
        if velas is None:
            return resultado
        ventana: ListaDoble[float] = ListaDoble()
        suma = 0.0
        for vela in velas:
            ventana.agregar_final(vela.cierre)
            suma += vela.cierre
            if ventana.tamanio() > self.periodo:
                suma -= ventana.primero()
                ventana.conservar_ultimos(self.periodo)
            if ventana.tamanio() == self.periodo:
                resultado.agregar_final(PuntoIndicador(vela.tiempo_apertura, suma / self.periodo))
        return resultado


class Ema(Indicador):
    """Media móvil exponencial (EMA) de los cierres.

    Fórmula: α = 2 / (p + 1). La primera EMA es la media simple de los primeros p
    cierres (en la vela p − 1); después EMAₜ = α·cierreₜ + (1 − α)·EMAₜ₋₁. Da más
    peso a los precios recientes que la SMA. Con p = 1 es igual al cierre.
    Complejidad: O(n), un recorrido hacia adelante.
    """

    def __init__(self, periodo: int) -> None:
        """Raises: ValueError si el periodo es menor que 1."""
        self.periodo = series.validar_periodo(periodo)

    def nombre(self) -> str:
        return "ema"

    def parametros(self) -> dict[str, object]:
        return {"periodo": self.periodo}

    def calcular(self, velas: ListaDoble[Vela] | None) -> Serie:
        """Complejidad: O(n)."""
        return series.ema(series.cierres(velas), self.periodo)
