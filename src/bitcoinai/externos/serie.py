"""Una serie de tiempo externa (miedo y codicia, financiación, DVOL) guardada en un árbol AVL."""

from bitcoinai.estructuras import ArbolAVL


class SerieTemporal:
    """Valores con su momento (ms), para preguntar "¿cuánto valía en tal momento?".

    Cada valor se guarda con el momento en que **ya se conocía** (no cuando empezó su
    periodo): así una vela nunca usa un dato que en su momento todavía no existía.
    ``valor_en(t)`` es el ``piso`` del árbol: el último valor conocido en ``t`` o antes,
    en O(log n), aunque las fuentes publiquen cada 8 horas o cada día y las velas sean
    de 15 minutos.
    """

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre
        self._arbol: ArbolAVL[int, float] = ArbolAVL()

    def agregar(self, conocido_en: int, valor: float) -> None:
        """Complejidad: O(log n)."""
        self._arbol.insertar(conocido_en, valor)

    def valor_en(self, momento: int) -> float | None:
        """El último valor conocido en ``momento`` (o None si la serie empieza después). O(log n)."""
        par = self._arbol.piso(momento)
        return None if par is None else par[1]

    def desde(self) -> int | None:
        """El primer momento con dato."""
        return None if self._arbol.esta_vacio() else self._arbol.minimo()[0]

    def ultimo(self) -> tuple[int, float] | None:
        return None if self._arbol.esta_vacio() else self._arbol.maximo()

    def tamanio(self) -> int:
        return self._arbol.tamanio()
