"""Bandas de Bollinger."""

import math
from dataclasses import dataclass

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import series
from bitcoinai.indicadores.base import Indicador, PuntoIndicador, Serie
from bitcoinai.modelo import Vela


@dataclass(frozen=True, slots=True)
class ResultadoBollinger:
    """Las tres series de las Bandas de Bollinger, alineadas punto a punto.

    Atributos:
        media: media móvil simple.
        superior: media + k·desviación.
        inferior: media − k·desviación.
    """

    media: Serie
    superior: Serie
    inferior: Serie


class BandasBollinger(Indicador):
    """Bandas de Bollinger.

    Fórmula, sobre los últimos p cierres:
        - media = SMA(p);
        - σ = desviación estándar poblacional = √(Σx²/p − media²), como en la definición de Bollinger;
        - superior = media + k·σ; inferior = media − k·σ.

    Valores habituales: p = 20, k = 2.

    Como la SMA, usa una ventana ListaDoble con suma y suma de cuadrados
    acumuladas: O(n) en total. Para no perder precisión al restar números grandes
    (precios de ~80 000 al cuadrado), los cierres se guardan desplazados restándoles
    el primero; la varianza no cambia con ese desplazamiento.
    """

    def __init__(self, periodo: int = 20, desviaciones: float = 2.0) -> None:
        """Raises: ValueError si el periodo es menor que 1 o las desviaciones no son positivas."""
        self.periodo = series.validar_periodo(periodo)
        if not (desviaciones > 0 and math.isfinite(desviaciones)):
            raise ValueError(f"Las desviaciones deben ser un número positivo: {desviaciones}")
        self.desviaciones = desviaciones

    def nombre(self) -> str:
        return "bollinger"

    def parametros(self) -> dict[str, object]:
        return {"periodo": self.periodo, "desviaciones": self.desviaciones}

    def calcular_bandas(self, velas: ListaDoble[Vela] | None) -> ResultadoBollinger:
        """Las tres bandas. Complejidad: O(n) en tiempo, O(p) en memoria extra."""
        media: Serie = ListaDoble()
        superior: Serie = ListaDoble()
        inferior: Serie = ListaDoble()
        if velas is None or velas.esta_vacia():
            return ResultadoBollinger(media, superior, inferior)
        p = self.periodo
        referencia = velas.primero().cierre
        ventana: ListaDoble[float] = ListaDoble()
        suma = 0.0
        suma_cuadrados = 0.0
        for vela in velas:
            x = vela.cierre - referencia
            ventana.agregar_final(x)
            suma += x
            suma_cuadrados += x * x
            if ventana.tamanio() > p:
                viejo = ventana.primero()
                suma -= viejo
                suma_cuadrados -= viejo * viejo
                ventana.conservar_ultimos(p)
            if ventana.tamanio() == p:
                media_desplazada = suma / p
                varianza = max(0.0, suma_cuadrados / p - media_desplazada * media_desplazada)
                banda = self.desviaciones * math.sqrt(varianza)
                valor_media = media_desplazada + referencia
                tiempo = vela.tiempo_apertura
                media.agregar_final(PuntoIndicador(tiempo, valor_media))
                superior.agregar_final(PuntoIndicador(tiempo, valor_media + banda))
                inferior.agregar_final(PuntoIndicador(tiempo, valor_media - banda))
        return ResultadoBollinger(media, superior, inferior)

    def calcular(self, velas: ListaDoble[Vela] | None) -> Serie:
        """La serie principal es la media. Complejidad: O(n)."""
        return self.calcular_bandas(velas).media

    def calcular_series(self, velas: ListaDoble[Vela]) -> dict[str, Serie]:
        """``media``, ``superior`` e ``inferior``. Complejidad: O(n)."""
        bandas = self.calcular_bandas(velas)
        return {"media": bandas.media, "superior": bandas.superior, "inferior": bandas.inferior}
