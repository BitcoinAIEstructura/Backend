"""Árbol de decisión (CART) con impureza de Gini, hecho a mano."""

from __future__ import annotations

from dataclasses import dataclass

from bitcoinai.estructuras import Lista
from bitcoinai.ia.base import Explicacion, Vector, por_peso, porcentaje
from bitcoinai.ia.caracteristicas import NOMBRES, Muestra

UMBRALES_POR_CARACTERISTICA = 15
"""Cortes que se prueban por característica (parejos entre su mínimo y su máximo en el nodo)."""


@dataclass(slots=True)
class NodoDecision:
    """Una pregunta ("¿RSI 14 ≤ 32,1?") o, si no tiene hijos, una hoja con la probabilidad."""

    muestras: int
    probabilidad: float  # de que suba, con suavizado de Laplace: (subidas + 1) / (n + 2)
    caracteristica: int | None = None
    umbral: float = 0.0
    si: NodoDecision | None = None  # ≤ umbral
    no: NodoDecision | None = None  # > umbral

    @property
    def es_hoja(self) -> bool:
        return self.caracteristica is None


def _gini(subidas: int, n: int) -> float:
    """Impureza de Gini con dos clases: 0 si todas iguales, 0,5 si mitad y mitad."""
    if n == 0:
        return 0.0
    p = subidas / n
    return 2 * p * (1 - p)


class ArbolDecision:
    """Árbol de preguntas sí/no sobre las características.

    En cada nodo prueba, para cada característica, varios cortes y elige el que más
    baja la impureza de Gini (que las dos mitades queden lo más "puras" posible).
    Para de dividir al llegar a ``profundidad_maxima`` o si quedarían menos de
    ``minimo_hoja`` muestras en un lado: un árbol muy profundo memoriza el ruido.
    Costo: O(profundidad · d · cortes · n).

    Explicación: el camino exacto que siguió la predicción, pregunta por pregunta,
    y qué tan seguido subió el precio en el entrenamiento al llegar a esa hoja.
    """

    nombre = "Árbol de decisión"

    def __init__(self, profundidad_maxima: int = 4, minimo_hoja: int = 20) -> None:
        self.profundidad_maxima = profundidad_maxima
        self.minimo_hoja = minimo_hoja
        self.raiz: NodoDecision | None = None
        self.importancia: Vector = (0.0,) * len(NOMBRES)

    def entrenar(self, muestras: Lista[Muestra]) -> None:
        if muestras.esta_vacia():
            raise ValueError("No hay muestras para entrenar")
        self.importancia = (0.0,) * len(muestras.obtener(0).caracteristicas)
        self.raiz = self._construir(muestras, 0)

    def _construir(self, muestras: Lista[Muestra], nivel: int) -> NodoDecision:
        n = muestras.tamanio()
        subidas = sum(m.etiqueta for m in muestras)
        nodo = NodoDecision(n, (subidas + 1) / (n + 2))
        if nivel >= self.profundidad_maxima or n < 2 * self.minimo_hoja or subidas in (0, n):
            return nodo
        mejor = self._mejor_corte(muestras, subidas)
        if mejor is None:
            return nodo
        j, umbral, ganancia = mejor
        si: Lista[Muestra] = Lista()
        no: Lista[Muestra] = Lista()
        for m in muestras:
            (si if m.caracteristicas[j] <= umbral else no).agregar(m)
        self.importancia = tuple(v + (ganancia * n if k == j else 0.0) for k, v in enumerate(self.importancia))
        nodo.caracteristica, nodo.umbral = j, umbral
        nodo.si = self._construir(si, nivel + 1)
        nodo.no = self._construir(no, nivel + 1)
        return nodo

    def _mejor_corte(self, muestras: Lista[Muestra], subidas: int) -> tuple[int, float, float] | None:
        """(característica, umbral, baja de Gini) del mejor corte que deja suficientes muestras a cada lado."""
        n = muestras.tamanio()
        base = _gini(subidas, n)
        mejor: tuple[int, float, float] | None = None
        d = len(muestras.obtener(0).caracteristicas)
        for j in range(d):
            minimo = min(m.caracteristicas[j] for m in muestras)
            maximo = max(m.caracteristicas[j] for m in muestras)
            if minimo == maximo:
                continue
            paso = (maximo - minimo) / (UMBRALES_POR_CARACTERISTICA + 1)
            for k in range(1, UMBRALES_POR_CARACTERISTICA + 1):
                umbral = minimo + k * paso
                n_si = subidas_si = 0
                for m in muestras:
                    if m.caracteristicas[j] <= umbral:
                        n_si += 1
                        subidas_si += m.etiqueta
                n_no = n - n_si
                if n_si < self.minimo_hoja or n_no < self.minimo_hoja:
                    continue
                impureza = (n_si * _gini(subidas_si, n_si) + n_no * _gini(subidas - subidas_si, n_no)) / n
                ganancia = base - impureza
                if ganancia > 1e-9 and (mejor is None or ganancia > mejor[2]):
                    mejor = (j, umbral, ganancia)
        return mejor

    def _hoja(self, x: Vector) -> tuple[NodoDecision, tuple[str, ...]]:
        if self.raiz is None:
            raise ValueError("El árbol no está entrenado")
        nodo = self.raiz
        pasos: tuple[str, ...] = ()
        while not nodo.es_hoja:
            assert nodo.caracteristica is not None and nodo.si is not None and nodo.no is not None
            valor = x[nodo.caracteristica]
            va_si = valor <= nodo.umbral
            pasos += (f"¿{NOMBRES[nodo.caracteristica]} ≤ {nodo.umbral:.4g}? Es {valor:.4g}: "
                      f"{'sí' if va_si else 'no'}.",)
            nodo = nodo.si if va_si else nodo.no
        return nodo, pasos

    def probabilidad(self, x: Vector) -> float:
        return self._hoja(x)[0].probabilidad

    def explicar(self, x: Vector) -> Explicacion:
        hoja, pasos = self._hoja(x)
        total = sum(self.importancia) or 1.0
        factores = por_peso((nombre, v / total) for nombre, v in zip(NOMBRES, self.importancia, strict=True) if v > 0)
        final = (f"Llegó a una hoja con {hoja.muestras} velas del entrenamiento: después de ellas "
                 f"subió el {porcentaje(hoja.probabilidad)} de las veces.")
        return Explicacion(resumen=final, factores=factores, pasos=(*pasos, final))

    def profundidad(self) -> int:
        def medir(nodo: NodoDecision | None) -> int:
            return 0 if nodo is None or nodo.es_hoja else 1 + max(medir(nodo.si), medir(nodo.no))
        return medir(self.raiz)
