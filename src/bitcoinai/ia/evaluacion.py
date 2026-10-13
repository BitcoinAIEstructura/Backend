"""Evaluación honesta: se entrena con el pasado y se mide con lo que vino después."""

from dataclasses import dataclass

from bitcoinai.estructuras import Lista
from bitcoinai.ia.base import Modelo
from bitcoinai.ia.caracteristicas import Muestra


def dividir_en_el_tiempo(muestras: Lista[Muestra],
                         fraccion_prueba: float = 0.2) -> tuple[Lista[Muestra], Lista[Muestra]]:
    """Las primeras para entrenar y las últimas para probar, sin mezclar.

    Mezclar al azar haría trampa: el modelo vería días posteriores a los que
    después "predice". Así se simula usarlo de verdad: solo con el pasado.
    """
    if not 0 < fraccion_prueba < 1:
        raise ValueError("La fracción de prueba debe estar entre 0 y 1")
    corte = round(muestras.tamanio() * (1 - fraccion_prueba))
    entrenamiento: Lista[Muestra] = Lista()
    prueba: Lista[Muestra] = Lista()
    for i, m in enumerate(muestras):
        (entrenamiento if i < corte else prueba).agregar(m)
    return entrenamiento, prueba


@dataclass(frozen=True, slots=True)
class Metricas:
    """Cómo le fue con datos que no vio.

    - ``exactitud``: aciertos ÷ predicciones.
    - ``base``: lo que acertaría "decir siempre lo que más pasó" en esas mismas velas.
      Superarla es lo mínimo para que el modelo aporte algo.
    - ``precision_sube``: de las veces que dijo "sube", cuántas subió (None si nunca lo dijo).
    """

    muestras: int
    exactitud: float
    base: float
    precision_sube: float | None
    veces_dijo_sube: int

    @property
    def ventaja(self) -> float:
        """Puntos de exactitud por encima de la base (negativo: peor que no hacer nada)."""
        return self.exactitud - self.base


def evaluar(modelo: Modelo, prueba: Lista[Muestra]) -> Metricas:
    """O(n · costo de predecir)."""
    if prueba.esta_vacia():
        raise ValueError("No hay muestras de prueba")
    aciertos = dijo_sube = acerto_sube = subidas = 0
    for m in prueba:
        sube = modelo.probabilidad(m.caracteristicas) >= 0.5
        aciertos += int(sube == bool(m.etiqueta))
        subidas += m.etiqueta
        if sube:
            dijo_sube += 1
            acerto_sube += m.etiqueta
    n = prueba.tamanio()
    return Metricas(n, aciertos / n, max(subidas, n - subidas) / n,
                    acerto_sube / dijo_sube if dijo_sube else None, dijo_sube)
