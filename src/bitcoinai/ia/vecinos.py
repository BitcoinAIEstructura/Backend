"""k vecinos más cercanos: "¿qué pasó después de las velas más parecidas a esta?"."""

import math
from datetime import UTC, datetime

from bitcoinai.estructuras import Lista, Monticulo
from bitcoinai.ia.base import Escalador, Explicacion, Vector, por_peso
from bitcoinai.ia.caracteristicas import NOMBRES, Muestra


def _fecha(milisegundos: int) -> str:
    return datetime.fromtimestamp(milisegundos / 1000, UTC).strftime("%Y-%m-%d %H:%M UTC")


class KVecinos:
    """No aprende fórmulas: guarda el pasado y, para predecir, busca los k más parecidos.

    "Parecido" es la distancia euclidiana entre características escaladas. Para
    elegir los k más cercanos sin ordenar todo, se usa un montículo de máximos de
    tamaño k: su tope es el más lejano de los elegidos y solo se reemplaza si llega
    uno más cerca. Además, la suma de cada distancia se corta en cuanto pasa a ese
    tope (ya no puede entrar). Predecir cuesta O(n · d + n log k) en el peor caso.

    La probabilidad es cuántos de esos k subieron después (con suavizado de Laplace).
    """

    nombre = "k vecinos"

    def __init__(self, k: int = 15) -> None:
        self.k = k
        self.escalador = Escalador()
        self.pasado: Lista[tuple[Vector, int, int]] = Lista()  # (x escalado, etiqueta, tiempo)

    def entrenar(self, muestras: Lista[Muestra]) -> None:
        self.escalador.ajustar(muestras)
        self.pasado = Lista()
        for m in muestras:
            self.pasado.agregar((self.escalador.transformar(m.caracteristicas), m.etiqueta, m.tiempo))

    def vecinos(self, x: Vector) -> Lista[tuple[float, int, int]]:
        """Los k más cercanos como (distancia, etiqueta, tiempo), del más cercano al más lejano."""
        if self.pasado.esta_vacia():
            raise ValueError("El modelo no está entrenado")
        escalado = self.escalador.transformar(x)
        cercanos: Monticulo[tuple[float, int, int]] = Monticulo(lambda v: v[0], mayor_primero=True, capacidad=self.k)
        for punto, etiqueta, tiempo in self.pasado:
            # Distancia al cuadrado (ordena igual que la distancia, sin raíz), y se abandona
            # en cuanto supera al más lejano de los k elegidos: ya no puede entrar.
            limite = cercanos.ver_tope()[0] if cercanos.tamanio() == self.k else math.inf
            cuadrado = 0.0
            for a, b in zip(punto, escalado, strict=True):
                cuadrado += (a - b) * (a - b)
                if cuadrado >= limite:
                    break
            else:
                if cercanos.tamanio() < self.k:
                    cercanos.insertar((cuadrado, etiqueta, tiempo))
                else:
                    cercanos.reemplazar_tope((cuadrado, etiqueta, tiempo))
        ordenados: Lista[tuple[float, int, int]] = Lista()
        while not cercanos.esta_vacia():
            cuadrado, etiqueta, tiempo = cercanos.extraer()  # salen del más lejano al más cercano
            ordenados.agregar_inicio((math.sqrt(cuadrado), etiqueta, tiempo))
        return ordenados

    def probabilidad(self, x: Vector) -> float:
        elegidos = self.vecinos(x)
        return (sum(e for _, e, _ in elegidos) + 1) / (elegidos.tamanio() + 2)

    def explicar(self, x: Vector) -> Explicacion:
        elegidos = self.vecinos(x)
        subieron = sum(e for _, e, _ in elegidos)
        pasos = tuple(
            f"{_fecha(t)} (distancia {d:.2f}): después {'subió' if e else 'no subió'}."
            for d, e, t in (elegidos.obtener(i) for i in range(min(3, elegidos.tamanio())))
        )
        # Lo que más distingue a esta vela: cuántas desviaciones se aleja del promedio en cada cosa.
        factores = por_peso(zip(NOMBRES, self.escalador.transformar(x), strict=True))
        resumen = (f"De las {elegidos.tamanio()} velas del pasado más parecidas a esta, "
                   f"{subieron} subieron después.")
        return Explicacion(resumen=resumen, factores=factores, pasos=(resumen, *pasos))
