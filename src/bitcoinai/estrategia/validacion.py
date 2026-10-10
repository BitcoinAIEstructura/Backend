"""Validación honesta de una estrategia con división entrenamiento/prueba."""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from bitcoinai.estrategia.backtest import Backtester, ResultadoBacktest
from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estructuras import Lista, ListaDoble
from bitcoinai.modelo import Vela

FRACCION_POR_DEFECTO = 0.7
"""Fracción de entrenamiento por defecto."""


@dataclass(frozen=True, slots=True)
class ResumenCandidato:
    """Cómo le fue a una combinación de parámetros en el periodo de entrenamiento."""

    parametros: dict[str, object]
    rentabilidad: float
    numero_operaciones: int


@dataclass(frozen=True, slots=True)
class ResultadoValidacion:
    """Resultado de la validación entrenamiento/prueba.

    ``entrenamiento`` es el backtest de los parámetros elegidos en entrenamiento;
    ``prueba`` es el de esos mismos parámetros en el periodo de prueba, nunca visto.
    """

    estrategia: str
    fraccion_entrenamiento: float
    velas_entrenamiento: int
    velas_prueba: int
    parametros_elegidos: dict[str, object]
    candidatos: Lista[ResumenCandidato]
    entrenamiento: ResultadoBacktest
    prueba: ResultadoBacktest


class ValidacionEntrenamientoPrueba:
    """Validación honesta con división entrenamiento/prueba.

    1. Las velas se dividen en dos tramos consecutivos: el primero (por defecto
       70 %) es el de entrenamiento y el resto el de prueba.
    2. Cada combinación de parámetros se prueba con un backtest **solo sobre las
       velas de entrenamiento** (se le entrega una lista sin ninguna vela de
       prueba), y se elige la de mayor rentabilidad.
    3. La elegida se prueba en el tramo de prueba, que nunca participó en la
       elección. Las velas de entrenamiento solo le sirven ahí como historial para
       calentar los indicadores, sin operar en ellas.

    Si a la estrategia le va mucho peor en prueba que en entrenamiento, los
    parámetros se ajustaron al pasado (sobreajuste).
    Complejidad: O(c · n), con c candidatos (cada backtest es O(n)).
    """

    def __init__(self, backtester: Backtester, fraccion_entrenamiento: float = FRACCION_POR_DEFECTO) -> None:
        """Raises: ValueError si la fracción no está entre 0 y 1 (sin incluirlos)."""
        if not 0 < fraccion_entrenamiento < 1:
            raise ValueError(f"La fracción de entrenamiento debe estar entre 0 y 1: {fraccion_entrenamiento}")
        self.backtester = backtester
        self.fraccion = fraccion_entrenamiento

    def ejecutar(self, candidatos: Iterable[Estrategia], velas: ListaDoble[Vela]) -> ResultadoValidacion:
        """Elige parámetros en entrenamiento y los mide en prueba.

        Raises:
            ValueError: si no hay candidatos.
        """
        # El 1e-9 evita que un error de redondeo (por ejemplo 83,999999…) quite una vela.
        cantidad_entrenamiento = math.floor(velas.tamanio() * self.fraccion + 1e-9)
        entrenamiento = _primeras(velas, cantidad_entrenamiento)

        resumenes: Lista[ResumenCandidato] = Lista()
        mejor: Estrategia | None = None
        mejor_resultado: ResultadoBacktest | None = None
        for candidato in candidatos:
            resultado = self.backtester.ejecutar(candidato, entrenamiento)
            resumenes.agregar(ResumenCandidato(candidato.parametros(), resultado.rentabilidad_total,
                                               resultado.numero_operaciones))
            if mejor_resultado is None or resultado.rentabilidad_total > mejor_resultado.rentabilidad_total:
                mejor, mejor_resultado = candidato, resultado
        if mejor is None or mejor_resultado is None:
            raise ValueError("Se necesita al menos un candidato")

        prueba = self.backtester.ejecutar(mejor, velas, cantidad_entrenamiento)
        return ResultadoValidacion(mejor.nombre(), self.fraccion, cantidad_entrenamiento,
                                   velas.tamanio() - cantidad_entrenamiento, mejor.parametros(),
                                   resumenes, mejor_resultado, prueba)


def _primeras(velas: ListaDoble[Vela], n: int) -> ListaDoble[Vela]:
    """Copia de las primeras n velas. Complejidad: O(n)."""
    copia: ListaDoble[Vela] = ListaDoble()
    for vela in velas:
        if copia.tamanio() == n:
            break
        copia.agregar_final(vela)
    return copia
