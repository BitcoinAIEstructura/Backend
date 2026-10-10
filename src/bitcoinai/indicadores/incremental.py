"""Calculadoras incrementales de indicadores: reciben un cierre a la vez, en O(1).

Hacen exactamente las mismas operaciones, en el mismo orden, que los
indicadores por lotes (``Sma``, ``Rsi``, ``Macd``), así que dan los mismos
valores. Las usan las estrategias para no recalcular todo desde la primera vela
en cada paso del backtest (que sería O(n²)): con ellas cada vela cuesta O(1).
"""

from bitcoinai.estructuras import ListaDoble


class SmaIncremental:
    """Media móvil simple que avanza de a un cierre.

    Guarda una ventana (ListaDoble) con los últimos p cierres y su suma.
    Complejidad de ``agregar``: O(1).
    """

    __slots__ = ("_suma", "_ventana", "periodo", "valor")

    def __init__(self, periodo: int) -> None:
        if periodo < 1:
            raise ValueError(f"El periodo debe ser al menos 1: {periodo}")
        self.periodo = periodo
        self._ventana: ListaDoble[float] = ListaDoble()
        self._suma = 0.0
        self.valor: float | None = None
        """Valor actual, o None mientras no hay p cierres."""

    def agregar(self, cierre: float) -> float | None:
        """Suma un cierre y devuelve la media actual (None durante el calentamiento)."""
        self._ventana.agregar_final(cierre)
        self._suma += cierre
        if self._ventana.tamanio() > self.periodo:
            self._suma -= self._ventana.primero()
            self._ventana.conservar_ultimos(self.periodo)
        self.valor = self._suma / self.periodo if self._ventana.tamanio() == self.periodo else None
        return self.valor


class EmaIncremental:
    """Media móvil exponencial que avanza de a un valor.

    Se inicializa con la media simple de los primeros p valores, como ``series.ema``.
    Complejidad de ``agregar``: O(1).
    """

    __slots__ = ("_alfa", "_suma", "_vistos", "periodo", "valor")

    def __init__(self, periodo: int) -> None:
        if periodo < 1:
            raise ValueError(f"El periodo debe ser al menos 1: {periodo}")
        self.periodo = periodo
        self._alfa = 2.0 / (periodo + 1)
        self._vistos = 0
        self._suma = 0.0
        self.valor: float | None = None

    def agregar(self, x: float) -> float | None:
        """Suma un valor y devuelve la EMA actual (None durante el calentamiento)."""
        if self._vistos < self.periodo:
            self._suma += x
            self._vistos += 1
            if self._vistos == self.periodo:
                self.valor = self._suma / self.periodo
        else:
            assert self.valor is not None
            self.valor = self._alfa * x + (1 - self._alfa) * self.valor
        return self.valor


class RsiIncremental:
    """RSI con suavizado de Wilder que avanza de a un cierre (mismos casos límite que ``Rsi``).

    Complejidad de ``agregar``: O(1).
    """

    __slots__ = ("_anterior", "_cambios", "_ganancia", "_perdida", "periodo", "valor")

    def __init__(self, periodo: int) -> None:
        if periodo < 1:
            raise ValueError(f"El periodo debe ser al menos 1: {periodo}")
        self.periodo = periodo
        self._anterior: float | None = None
        self._cambios = 0
        self._ganancia = 0.0
        self._perdida = 0.0
        self.valor: float | None = None

    def agregar(self, cierre: float) -> float | None:
        """Suma un cierre y devuelve el RSI actual (None durante el calentamiento)."""
        if self._anterior is not None:
            p = self.periodo
            cambio = cierre - self._anterior
            ganancia = max(cambio, 0.0)
            perdida = max(-cambio, 0.0)
            self._cambios += 1
            if self._cambios <= p:
                self._ganancia += ganancia
                self._perdida += perdida
                if self._cambios == p:
                    self._ganancia /= p
                    self._perdida /= p
                    self.valor = _rsi(self._ganancia, self._perdida)
            else:
                self._ganancia = (self._ganancia * (p - 1) + ganancia) / p
                self._perdida = (self._perdida * (p - 1) + perdida) / p
                self.valor = _rsi(self._ganancia, self._perdida)
        self._anterior = cierre
        return self.valor


class MacdIncremental:
    """MACD que avanza de a un cierre: línea MACD, señal e histograma.

    Complejidad de ``agregar``: O(1).
    """

    __slots__ = ("_lenta", "_rapida", "_senal", "histograma", "macd", "senal")

    def __init__(self, rapido: int, lento: int, senal: int) -> None:
        self._rapida = EmaIncremental(rapido)
        self._lenta = EmaIncremental(lento)
        self._senal = EmaIncremental(senal)
        self.macd: float | None = None
        self.senal: float | None = None
        self.histograma: float | None = None

    def agregar(self, cierre: float) -> None:
        """Suma un cierre y actualiza las tres series (None mientras falten datos)."""
        rapida = self._rapida.agregar(cierre)
        lenta = self._lenta.agregar(cierre)
        if rapida is None or lenta is None:
            return
        self.macd = rapida - lenta
        self.senal = self._senal.agregar(self.macd)
        if self.senal is not None:
            self.histograma = self.macd - self.senal


def _rsi(ganancia: float, perdida: float) -> float:
    if perdida == 0:
        return 50.0 if ganancia == 0 else 100.0
    return 100.0 - 100.0 / (1.0 + ganancia / perdida)
