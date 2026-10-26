"""Junta las fuentes externas con caché: series para entrenar y una foto de ahora para mostrar.

Si una fuente falla, las demás siguen: la IA entrena con lo que haya y la página dice
cuál no respondió. Las tres se piden a la vez (en hilos), porque cada una tarda.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TypeVar

from bitcoinai.externos.clientes import DIA_MS, HORA_MS, ClienteExternos, FuenteExternaError
from bitcoinai.externos.serie import SerieTemporal
from bitcoinai.modelo import Intervalo

LOG = logging.getLogger("bitcoinai.externos")

DURACION_CACHE_S = 3600.0
DURACION_CACHE_RAPIDA_S = 600.0
SEGUNDOS_POR_ANIO = 365 * 24 * 3600

CLASIFICACION = {
    "Extreme Fear": "miedo extremo",
    "Fear": "miedo",
    "Neutral": "neutral",
    "Greed": "codicia",
    "Extreme Greed": "codicia extrema",
}

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class SeriesExternas:
    """Las series para entrenar (None si esa fuente no respondió) y por qué faltan."""

    miedo_codicia: SerieTemporal | None
    financiacion: SerieTemporal | None
    dvol: SerieTemporal | None
    errores: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Lectura:
    """Un dato de ahora, explicado para quien empieza."""

    id: str
    nombre: str
    fuente: str
    valor: float
    valor_texto: str
    explicacion: str


@dataclass(frozen=True, slots=True)
class Panorama:
    lecturas: tuple[Lectura, ...]
    errores: dict[str, str]
    actualizado_en: int


def resolucion_dvol(intervalo: Intervalo) -> str:
    """Datos por hora para velas cortas; cada 12 h para las de 4 h; diarios para las de 1 día."""
    if intervalo.milisegundos >= DIA_MS:
        return "1D"
    if intervalo.milisegundos >= 4 * HORA_MS:
        return "43200"
    return "3600"


def movimiento_esperado(dvol: float, segundos: float) -> float:
    """Cuánto se espera que se mueva el precio (una desviación, ~68 % de las veces) en ``segundos``.

    El DVOL es la volatilidad anual en %: se escala con la raíz del tiempo. Con DVOL 40 y
    una vela de 1 hora: 0,40 × √(3600 / 31 536 000) ≈ 0,43 %.
    """
    return dvol / 100 * math.sqrt(segundos / SEGUNDOS_POR_ANIO)


def porcentaje(fraccion: float, decimales: int = 1) -> str:
    return f"{fraccion * 100:.{decimales}f} %".replace(".", ",")


def usdt(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


class DatosExternos:
    """Fuentes externas con caché: una hora para las series y 10 minutos para lo de ahora."""

    def __init__(self, cliente: ClienteExternos | None = None, reloj: Callable[[], float] = time.time,
                 duracion_cache_s: float = DURACION_CACHE_S) -> None:
        self._cliente = cliente or ClienteExternos()
        self._reloj = reloj
        self._duracion = duracion_cache_s
        self._cache: dict[str, tuple[float, int, object]] = {}  # clave → (guardado, desde, dato)
        self._candado = threading.Lock()

    def _guardado(self, clave: str, desde: int, duracion: float) -> object | None:
        with self._candado:
            fila = self._cache.get(clave)
        if fila is None:
            return None
        guardado, cubre_desde, dato = fila
        return dato if self._reloj() - guardado < duracion and cubre_desde <= desde else None

    def _guardar(self, clave: str, desde: int, dato: object) -> None:
        with self._candado:
            self._cache[clave] = (self._reloj(), desde, dato)

    def _con_cache(self, clave: str, desde: int, duracion: float, pedir: Callable[[], T]) -> T:
        guardado = self._guardado(clave, desde, duracion)
        if guardado is not None:
            return guardado  # type: ignore[return-value]
        dato = pedir()
        self._guardar(clave, desde, dato)
        return dato

    def series(self, desde_ms: int, intervalo: Intervalo) -> SeriesExternas:
        """Las tres series desde ``desde_ms`` (un poco antes, para los cambios de 7 días)."""
        ahora = int(self._reloj() * 1000)
        desde = desde_ms - 8 * DIA_MS
        resolucion = resolucion_dvol(intervalo)
        tareas: dict[str, Callable[[], SerieTemporal]] = {
            "miedo-codicia": lambda: self._con_cache("fng", 0, self._duracion,
                                                     lambda: self._cliente.miedo_codicia()[0]),
            "financiacion": lambda: self._con_cache("financiacion", desde, self._duracion,
                                                    lambda: self._cliente.financiacion(desde, ahora)),
            "dvol": lambda: self._con_cache(f"dvol-{resolucion}", desde, self._duracion,
                                            lambda: self._cliente.dvol(desde, ahora, resolucion)),
        }
        resultados, errores = self._en_paralelo(tareas)
        return SeriesExternas(resultados.get("miedo-codicia"), resultados.get("financiacion"),
                              resultados.get("dvol"), errores)

    def _en_paralelo(self, tareas: dict[str, Callable[[], T]]) -> tuple[dict[str, T], dict[str, str]]:
        resultados: dict[str, T] = {}
        errores: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=len(tareas)) as hilos:
            futuros = {nombre: hilos.submit(tarea) for nombre, tarea in tareas.items()}
            for nombre, futuro in futuros.items():
                try:
                    resultados[nombre] = futuro.result()
                except FuenteExternaError as error:
                    LOG.warning("Fuente externa %s: %s", nombre, error)
                    errores[nombre] = str(error)
        return resultados, errores

    def panorama(self, intervalo: Intervalo, precio: float | None) -> Panorama:
        """Lo que dicen ahora las fuentes, con una explicación sencilla de cada dato."""
        ahora = int(self._reloj() * 1000)
        rapida = DURACION_CACHE_RAPIDA_S
        tareas: dict[str, Callable[[], object]] = {
            "miedo-codicia": lambda: self._con_cache("fng-ahora", 0, rapida, self._cliente.miedo_codicia),
            "financiacion": lambda: self._con_cache(
                "financiacion-ahora", 0, rapida, lambda: self._cliente.financiacion(ahora - 2 * DIA_MS, ahora)),
            "largos": lambda: self._con_cache("largos", 0, rapida, self._cliente.largos_y_cortos),
            "dvol": lambda: self._con_cache(
                "dvol-ahora", 0, rapida, lambda: self._cliente.dvol(ahora - 6 * HORA_MS, ahora, "3600")),
        }
        resultados, errores = self._en_paralelo(tareas)
        lecturas: tuple[Lectura, ...] = ()

        fng = resultados.get("miedo-codicia")
        if isinstance(fng, tuple):
            serie, clasificacion = fng
            ultimo = serie.ultimo() if isinstance(serie, SerieTemporal) else None
            if ultimo is not None:
                valor = ultimo[1]
                nombre = CLASIFICACION.get(str(clasificacion), str(clasificacion).lower())
                hoy = "Hoy está neutral" if nombre == "neutral" else f"Hoy hay {nombre}"
                lecturas += (Lectura(
                    "miedo-codicia", "Miedo y codicia", "alternative.me", valor, f"{valor:.0f} de 100 · {nombre}",
                    f"Mide el ánimo de la gente con Bitcoin. Cerca de 0 hay miedo (muchos venden); cerca de 100 hay "
                    f"euforia (muchos compran). {hoy}."),)

        financiacion = resultados.get("financiacion")
        if isinstance(financiacion, SerieTemporal) and (ultima := financiacion.ultimo()) is not None:
            tasa = ultima[1]
            quien = ("los que apuestan a que sube les pagan a los que apuestan a que baja: hay más optimismo"
                     if tasa > 0 else
                     "los que apuestan a que baja les pagan a los que apuestan a que sube: hay más pesimismo"
                     if tasa < 0 else "nadie le paga a nadie: está equilibrado")
            lecturas += (Lectura(
                "financiacion", "Financiación de futuros", "Binance (futuros)", tasa, porcentaje(tasa, 4),
                f"Cada 8 horas, en los futuros {quien}."),)

        largos = resultados.get("largos")
        if isinstance(largos, float):
            lecturas += (Lectura(
                "largos", "Cuentas que apuestan a que sube", "Binance (futuros)", largos, porcentaje(largos, 0),
                f"De cada 100 cuentas con futuros de Bitcoin, unas {largos * 100:.0f} apuestan a que sube. "
                "Ojo: que muchos apuesten igual no garantiza que acierten."),)

        dvol = resultados.get("dvol")
        if isinstance(dvol, SerieTemporal) and (ultimo_dvol := dvol.ultimo()) is not None:
            valor = ultimo_dvol[1]
            movimiento = movimiento_esperado(valor, intervalo.milisegundos / 1000)
            en_usdt = f" (unos ±{usdt(precio * movimiento)} USDT)" if precio else ""
            lecturas += (Lectura(
                "dvol", "Movimiento esperado", "Deribit (opciones)", valor,
                f"±{porcentaje(movimiento, 2)} por vela",
                f"Según las opciones de Deribit (volatilidad {valor:.0f} %), en la próxima vela el precio se "
                f"movería unos ±{porcentaje(movimiento, 2)}{en_usdt}, hacia arriba o hacia abajo. "
                "Dice cuánto se mueve, no hacia dónde."),)
        return Panorama(lecturas, errores, ahora)
