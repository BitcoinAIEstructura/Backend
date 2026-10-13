"""Predicciones de la IA para la vela siguiente, con métricas medidas en datos no vistos."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from bitcoinai.estructuras import Lista
from bitcoinai.ia.arbol import ArbolDecision, NodoDecision
from bitcoinai.ia.base import Explicacion, Modelo
from bitcoinai.ia.caracteristicas import construir_muestras
from bitcoinai.ia.comite import Comite
from bitcoinai.ia.evaluacion import Metricas, dividir_en_el_tiempo, evaluar, metricas_de
from bitcoinai.ia.logistica import RegresionLogistica
from bitcoinai.ia.vecinos import KVecinos
from bitcoinai.mercado import FuenteDeMercado, velas_cerradas
from bitcoinai.modelo import Intervalo

VELAS = 1000
DURACION_CACHE_S = 600.0
MINIMO_MUESTRAS = 200
AVISO = ("Predicción hecha con datos reales del pasado. El mercado es en gran parte impredecible: ninguna "
         "exactitud pasada garantiza la siguiente. No es asesoría financiera.")

FABRICAS: tuple[Callable[[], Modelo], ...] = (RegresionLogistica, ArbolDecision, KVecinos)


class DatosInsuficientesError(ValueError):
    """No hay velas suficientes para entrenar con honestidad."""


@dataclass(frozen=True, slots=True)
class ResultadoModelo:
    nombre: str
    probabilidad: float
    explicacion: Explicacion
    metricas: Metricas
    peso: float | None = None  # en el comité; None para el propio comité

    @property
    def direccion(self) -> str:
        return "SUBE" if self.probabilidad >= 0.5 else "BAJA"

    @property
    def confianza(self) -> float:
        """0 si dice 50 %, 1 si dice 0 % o 100 %."""
        return abs(self.probabilidad - 0.5) * 2


@dataclass(frozen=True, slots=True)
class PuntoPrueba:
    """Una vela del periodo de prueba: qué dijo el comité y qué pasó."""

    tiempo: int
    probabilidad: float
    subio: bool


@dataclass(frozen=True, slots=True)
class PrediccionIA:
    intervalo: str
    tiempo_vela: int
    entrenado_en: int
    muestras_entrenamiento: int
    muestras_prueba: int
    modelos: tuple[ResultadoModelo, ...]
    comite: ResultadoModelo
    prueba: Lista[PuntoPrueba]
    caracteristicas: tuple[float, ...]  # las de la vela de ahora, en el orden de NOMBRES
    arbol: NodoDecision | None  # el árbol entrenado, para dibujarlo
    aviso: str = AVISO


class ServicioIA:
    """Entrena, mide y predice; guarda el resultado de cada intervalo unos minutos.

    Entrenar cuesta unos segundos, así que un candado evita entrenar dos veces lo
    mismo a la vez y la caché (un ``dict`` por intervalo) sirve las peticiones
    siguientes. Los modelos se entrenan con el 80 % más viejo y se miden con el 20 %
    más reciente: el modelo que predice es el mismo que se midió.
    """

    def __init__(self, fuente: FuenteDeMercado, simbolo: str, duracion_cache_s: float = DURACION_CACHE_S,
                 reloj: Callable[[], float] = time.time) -> None:
        self._fuente = fuente
        self._simbolo = simbolo
        self._duracion = duracion_cache_s
        self._reloj = reloj
        self._cache: dict[str, PrediccionIA] = {}
        self._candado = threading.Lock()

    def predecir(self, intervalo: Intervalo) -> PrediccionIA:
        """Raises: DatosInsuficientesError, MercadoError."""
        with self._candado:
            guardada = self._cache.get(intervalo.codigo)
            if guardada is not None and self._reloj() - guardada.entrenado_en / 1000 < self._duracion:
                return guardada
            nueva = self._entrenar(intervalo)
            self._cache[intervalo.codigo] = nueva
            return nueva

    def _entrenar(self, intervalo: Intervalo) -> PrediccionIA:
        ahora = self._reloj()
        velas = velas_cerradas(self._fuente.obtener_velas(self._simbolo, intervalo, VELAS), int(ahora * 1000))
        muestras, ultima, tiempo_ultima = construir_muestras(velas)
        if ultima is None or tiempo_ultima is None or muestras.tamanio() < MINIMO_MUESTRAS:
            raise DatosInsuficientesError(
                f"Hacen falta al menos {MINIMO_MUESTRAS} velas para entrenar; hay {muestras.tamanio()}")
        entrenamiento, prueba = dividir_en_el_tiempo(muestras, 0.2)

        comite = Comite(FABRICAS)
        comite.entrenar(entrenamiento)
        resultados: tuple[ResultadoModelo, ...] = ()
        for modelo, peso in zip(comite.miembros, comite.pesos, strict=True):
            resultados += (ResultadoModelo(modelo.nombre, modelo.probabilidad(ultima), modelo.explicar(ultima),
                                           evaluar(modelo, prueba), peso),)
        # Las probabilidades del comité en la prueba se calculan una vez: sirven para sus
        # métricas y para la gráfica de aciertos.
        puntos: Lista[PuntoPrueba] = Lista()
        pares: Lista[tuple[float, int]] = Lista()
        for m in prueba:
            probabilidad = comite.probabilidad(m.caracteristicas)
            puntos.agregar(PuntoPrueba(m.tiempo, probabilidad, bool(m.etiqueta)))
            pares.agregar((probabilidad, m.etiqueta))
        del_comite = ResultadoModelo(comite.nombre, comite.probabilidad(ultima), comite.explicar(ultima),
                                     metricas_de(pares))
        arbol = next((m.raiz for m in comite.miembros if isinstance(m, ArbolDecision)), None)
        return PrediccionIA(intervalo.codigo, tiempo_ultima, int(ahora * 1000), entrenamiento.tamanio(),
                            prueba.tamanio(), resultados, del_comite, puntos, ultima, arbol)
