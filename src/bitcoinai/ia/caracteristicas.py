"""De velas a ejemplos para aprender: características de cada vela y si la siguiente subió.

Cada característica usa solo la vela actual y las anteriores (nunca el futuro). La
etiqueta es lo único que mira adelante: 1 si la vela siguiente cerró más arriba.
Las velas se copian a ``Arreglo`` para leer "hace 5 velas" en O(1).
"""

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from bitcoinai.estructuras import Arreglo, Lista
from bitcoinai.externos import SeriesExternas, SerieTemporal
from bitcoinai.modelo import Vela

HORA_MS = 3_600_000
DIA_MS = 24 * HORA_MS

NOMBRES: tuple[str, ...] = (
    "Rendimiento de la última vela",
    "Rendimiento de 5 velas",
    "Rendimiento de 20 velas",
    "RSI 14",
    "Histograma del MACD",
    "Volatilidad de 20 velas",
    "Distancia a la SMA 20",
    "SMA 20 frente a SMA 50",
    "Volumen relativo",
    "Rango de la vela",
)
"""Nombre de cada característica, en el orden del vector."""

@dataclass(frozen=True, slots=True)
class FuenteCaracteristicas:
    """Una fuente externa y las características que aporta."""

    id: str
    nombre: str
    caracteristicas: tuple[str, ...]


FUENTES_EXTERNAS: tuple[FuenteCaracteristicas, ...] = (
    FuenteCaracteristicas("miedo-codicia", "Índice de miedo y codicia",
                          ("Miedo y codicia", "Cambio del miedo y codicia en 7 días")),
    FuenteCaracteristicas("financiacion", "Financiación de futuros (Binance)",
                          ("Financiación de futuros", "Financiación promedio de 24 h")),
    FuenteCaracteristicas("dvol", "Volatilidad esperada (Deribit)",
                          ("Volatilidad esperada (DVOL)", "Cambio del DVOL en 24 h")),
)


def _miedo_codicia(serie: SerieTemporal, t: int) -> tuple[float, ...] | None:
    ahora, antes = serie.valor_en(t), serie.valor_en(t - 7 * DIA_MS)
    return None if ahora is None or antes is None else (ahora / 100, (ahora - antes) / 100)


def _financiacion(serie: SerieTemporal, t: int) -> tuple[float, ...] | None:
    # En "por mil" para que no sean números diminutos (0,0001 → 0,1).
    valores = tuple(serie.valor_en(t - k * 8 * HORA_MS) for k in range(3))
    if any(v is None for v in valores):
        return None
    tasas = tuple(v for v in valores if v is not None)
    return tasas[0] * 1000, sum(tasas) / 3 * 1000


def _dvol(serie: SerieTemporal, t: int) -> tuple[float, ...] | None:
    ahora, antes = serie.valor_en(t), serie.valor_en(t - DIA_MS)
    return None if ahora is None or antes is None else (ahora / 100, (ahora - antes) / 100)


_LEER: dict[str, Callable[[SerieTemporal, int], tuple[float, ...] | None]] = {
    "miedo-codicia": _miedo_codicia,
    "financiacion": _financiacion,
    "dvol": _dvol,
}


def _serie_de(externos: SeriesExternas, fuente: str) -> SerieTemporal | None:
    return {"miedo-codicia": externos.miedo_codicia, "financiacion": externos.financiacion,
            "dvol": externos.dvol}[fuente]


CALENTAMIENTO = 50
"""Velas necesarias antes de la primera muestra (la SMA 50 necesita 50)."""


@dataclass(frozen=True, slots=True)
class Muestra:
    """Un ejemplo: las características de una vela y qué pasó en la siguiente."""

    tiempo: int
    caracteristicas: tuple[float, ...]
    etiqueta: int  # 1 = la siguiente subió; 0 = no subió


class _Series:
    """Cierres, volúmenes, máximos y mínimos en arreglos, más los indicadores que se arrastran."""

    def __init__(self, velas: Iterable[Vela]) -> None:
        copia: Lista[Vela] = Lista()
        for v in velas:
            copia.agregar(v)
        n = copia.tamanio()
        self.n = n
        self.velas: Arreglo[Vela] = Arreglo(n)
        self.cierre: Arreglo[float] = Arreglo(n)
        self.volumen: Arreglo[float] = Arreglo(n)
        self.rsi: Arreglo[float] = Arreglo(n)
        self.histograma: Arreglo[float] = Arreglo(n)
        for i, v in enumerate(copia):
            self.velas.poner(i, v)
            self.cierre.poner(i, v.cierre)
            self.volumen.poner(i, v.volumen)
        self._calcular_rsi(14)
        self._calcular_macd(12, 26, 9)

    def c(self, i: int) -> float:
        valor = self.cierre.obtener(i)
        assert valor is not None
        return valor

    def _calcular_rsi(self, periodo: int) -> None:
        """RSI de Wilder, vela por vela: O(n)."""
        ganancia = perdida = 0.0
        for i in range(1, self.n):
            cambio = self.c(i) - self.c(i - 1)
            sube, baja = max(cambio, 0.0), max(-cambio, 0.0)
            if i <= periodo:
                ganancia += sube / periodo
                perdida += baja / periodo
            else:
                ganancia = (ganancia * (periodo - 1) + sube) / periodo
                perdida = (perdida * (periodo - 1) + baja) / periodo
            rsi = 100.0 if perdida == 0 else 100 - 100 / (1 + ganancia / perdida)
            self.rsi.poner(i, rsi)

    def _calcular_macd(self, rapido: int, lento: int, senal: int) -> None:
        """Histograma del MACD dividido entre el precio (así se compara en cualquier época). O(n)."""
        if self.n == 0:
            return
        k_r, k_l, k_s = 2 / (rapido + 1), 2 / (lento + 1), 2 / (senal + 1)
        ema_r = ema_l = self.c(0)
        ema_s = 0.0
        for i in range(self.n):
            ema_r += k_r * (self.c(i) - ema_r)
            ema_l += k_l * (self.c(i) - ema_l)
            macd = ema_r - ema_l
            ema_s += k_s * (macd - ema_s)
            self.histograma.poner(i, (macd - ema_s) / self.c(i))

    def media(self, arreglo: Arreglo[float], hasta: int, cuantas: int) -> float:
        """Promedio de las ``cuantas`` posiciones que terminan en ``hasta``. O(cuantas)."""
        suma = 0.0
        for j in range(hasta - cuantas + 1, hasta + 1):
            valor = arreglo.obtener(j)
            suma += 0.0 if valor is None else valor
        return suma / cuantas

    def caracteristicas(self, i: int) -> tuple[float, ...]:
        c = self.c
        rendimientos = Lista[float]()
        for j in range(i - 19, i + 1):
            rendimientos.agregar(c(j) / c(j - 1) - 1)
        promedio = sum(rendimientos) / 20
        volatilidad = math.sqrt(sum((r - promedio) ** 2 for r in rendimientos) / 20)
        sma20 = self.media(self.cierre, i, 20)
        sma50 = self.media(self.cierre, i, 50)
        volumen_medio = self.media(self.volumen, i, 20)
        vela = self.velas.obtener(i)
        assert vela is not None
        rsi = self.rsi.obtener(i)
        histograma = self.histograma.obtener(i)
        return (
            c(i) / c(i - 1) - 1,
            c(i) / c(i - 5) - 1,
            c(i) / c(i - 20) - 1,
            50.0 if rsi is None else rsi,
            0.0 if histograma is None else histograma,
            volatilidad,
            c(i) / sma20 - 1,
            sma20 / sma50 - 1,
            vela.volumen / volumen_medio - 1 if volumen_medio > 0 else 0.0,
            (vela.maximo - vela.minimo) / c(i),
        )


@dataclass(frozen=True, slots=True)
class Conjunto:
    """Las muestras para aprender y lo necesario para predecir la vela de ahora.

    ``nombres`` dice qué es cada posición del vector (las 10 del precio y, al final, las
    de las fuentes externas que se pudieron usar). ``fuentes_usadas`` y ``fuentes_omitidas``
    explican cuáles entraron: una fuente entra solo si tiene dato para **todas** las velas
    (rellenar huecos inventaría información).
    """

    muestras: Lista[Muestra]
    ultima: tuple[float, ...] | None
    tiempo_ultima: int | None
    nombres: tuple[str, ...]
    fuentes_usadas: tuple[str, ...]
    fuentes_omitidas: dict[str, str]


def construir_conjunto(velas: Iterable[Vela], externos: SeriesExternas | None = None) -> Conjunto:
    """Como ``construir_muestras``, sumando las características de las fuentes externas.

    Cada dato externo se toma en el **cierre** de la vela con el último valor ya conocido
    (``SerieTemporal.valor_en``): nunca se usa algo que en ese momento no se sabía.
    """
    copia: Lista[Vela] = Lista()
    for v in velas:
        copia.agregar(v)
    base, ultima, tiempo_ultima = construir_muestras(copia)
    s = _Series(copia)
    nombres = NOMBRES
    usadas: tuple[str, ...] = ()
    omitidas: dict[str, str] = {} if externos is None else dict(externos.errores)
    if externos is None or ultima is None:
        return Conjunto(base, ultima, tiempo_ultima, nombres, usadas, omitidas)
    # Cierre de cada vela que entra (las muestras y la última).
    cierres: Lista[int] = Lista()
    for i in range(CALENTAMIENTO, s.n):
        vela = s.velas.obtener(i)
        assert vela is not None
        cierres.agregar(vela.tiempo_cierre)
    # Cada columna en un Arreglo: leer la posición i es O(1) (en una Lista sería O(i)).
    columnas: Lista[Arreglo[tuple[float, ...]]] = Lista()
    for fuente in FUENTES_EXTERNAS:
        serie = _serie_de(externos, fuente.id)
        if serie is None:
            omitidas.setdefault(fuente.id, "No respondió")
            continue
        leer = _LEER[fuente.id]
        columna: Arreglo[tuple[float, ...]] = Arreglo(cierres.tamanio())
        completa = True
        for posicion, t in enumerate(cierres):
            valores = leer(serie, t)
            if valores is None:
                completa = False
                break
            columna.poner(posicion, valores)
        if not completa:
            omitidas[fuente.id] = "Su historial no alcanza a cubrir todas las velas"
            continue
        columnas.agregar(columna)
        nombres += fuente.caracteristicas
        usadas += (fuente.id,)
    if columnas.esta_vacia():
        return Conjunto(base, ultima, tiempo_ultima, nombres, usadas, omitidas)

    def extra(posicion: int) -> tuple[float, ...]:
        valores: tuple[float, ...] = ()
        for columna in columnas:
            valor = columna.obtener(posicion)
            assert valor is not None
            valores += valor
        return valores

    muestras: Lista[Muestra] = Lista()
    for posicion, m in enumerate(base):
        muestras.agregar(Muestra(m.tiempo, m.caracteristicas + extra(posicion), m.etiqueta))
    return Conjunto(muestras, ultima + extra(cierres.tamanio() - 1), tiempo_ultima, nombres, usadas, omitidas)


def construir_muestras(velas: Iterable[Vela]) -> tuple[Lista[Muestra], tuple[float, ...] | None, int | None]:
    """Las muestras de aprendizaje y las características de la última vela (para predecir).

    Returns:
        ``(muestras, ultima, tiempo_ultima)``. La última vela no tiene etiqueta (no se
        sabe qué viene), por eso va aparte. ``ultima`` es None si no hay velas suficientes.
    """
    s = _Series(velas)
    muestras: Lista[Muestra] = Lista()
    for i in range(CALENTAMIENTO, s.n - 1):
        vela = s.velas.obtener(i)
        assert vela is not None
        muestras.agregar(Muestra(vela.tiempo_apertura, s.caracteristicas(i), int(s.c(i + 1) > s.c(i))))
    if s.n <= CALENTAMIENTO:
        return muestras, None, None
    ultima = s.velas.obtener(s.n - 1)
    assert ultima is not None
    return muestras, s.caracteristicas(s.n - 1), ultima.tiempo_apertura
