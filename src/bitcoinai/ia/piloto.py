"""Piloto automático: el comité de la IA decide qué hacer y cuánto arriesgar.

Es lo que usa el bot en el modo "Piloto IA" y lo que muestra el consejo de la IA en el
panel, la cartera y las órdenes. Todo es simulado: nunca opera con dinero real.

Cómo decide (con la predicción del comité para la vela siguiente):

1. **Señal.** Si la probabilidad de que suba es 55 % o más, COMPRAR; si es 45 % o menos,
   VENDER; en medio, MANTENER (no hay ventaja clara).
2. **Riesgo.** Del tope del usuario usa una parte que crece con la confianza (mínimo un
   cuarto del tope). Si en las velas de prueba el comité no le ganó a la base, usa la
   mitad: la IA es prudente cuando no ha demostrado nada.
3. **Stop-loss y take-profit.** Salen de la volatilidad reciente (desviación típica de los
   rendimientos de las últimas velas): stop-loss = 3 × volatilidad y take-profit = 2 ×
   stop-loss, sin pasar los topes del usuario. Así, con el mercado tranquilo protege más
   cerca y con el mercado agitado da más aire.
"""

import math
import time
from collections.abc import Callable

from bitcoinai.ia.servicio import PrediccionIA, ServicioIA
from bitcoinai.mercado import FuenteDeMercado, velas_cerradas
from bitcoinai.modelo import Intervalo
from bitcoinai.simulacion.interfaces import ConsejoPiloto, LimitesPiloto

UMBRAL_COMPRA = 0.55
UMBRAL_VENTA = 0.45
VELAS_VOLATILIDAD = 48
STOP_MINIMO = 0.01
TAKE_MINIMO = 0.02
RIESGO_MINIMO = 0.01

INTERVALOS_IA = ("15m", "1h", "4h", "1d")
"""Los intervalos en que la IA sabe predecir; con 1m o 5m se usa 15m."""

NOMBRE_INTERVALO = {"15m": "15 minutos", "1h": "1 hora", "4h": "4 horas", "1d": "1 día"}


def intervalo_ia(codigo: str) -> str:
    """El intervalo de la IA más cercano al del bot."""
    return codigo if codigo in INTERVALOS_IA else "15m"


def volatilidad(cierres: tuple[float, ...]) -> float:
    """Desviación típica de los rendimientos entre cierres seguidos. Complejidad: O(n)."""
    if len(cierres) < 3:
        return 0.0
    rendimientos = tuple(b / a - 1 for a, b in zip(cierres, cierres[1:], strict=False) if a > 0)
    media = sum(rendimientos) / len(rendimientos)
    return math.sqrt(sum((r - media) ** 2 for r in rendimientos) / (len(rendimientos) - 1))


def _porcentaje(valor: float, decimales: int = 0) -> str:
    return f"{valor * 100:.{decimales}f}".replace(".", ",") + " %"


def decidir(prediccion: PrediccionIA, vol: float, precio: float, limites: LimitesPiloto) -> ConsejoPiloto:
    """La decisión del piloto con una predicción ya hecha (función pura, fácil de probar)."""
    comite = prediccion.comite
    p = comite.probabilidad
    confianza = comite.confianza
    metricas = comite.metricas
    gana = metricas.ventaja > 0
    if p >= UMBRAL_COMPRA:
        senal = "COMPRAR"
    elif p <= UMBRAL_VENTA:
        senal = "VENDER"
    else:
        senal = "MANTENER"
    factor = max(0.25, min(1.0, confianza * 2.5)) * (1.0 if gana else 0.5)
    riesgo = max(min(RIESGO_MINIMO, limites.riesgo), min(limites.riesgo, limites.riesgo * factor))
    stop = min(limites.stop_loss, max(STOP_MINIMO, 3 * vol))
    take = min(limites.take_profit, max(TAKE_MINIMO, 2 * stop))
    nombre = NOMBRE_INTERVALO.get(prediccion.intervalo, prediccion.intervalo)
    prueba = (f"en velas que no vio acertó {_porcentaje(metricas.exactitud)} (la base, {_porcentaje(metricas.base)})"
              if metricas.muestras else "aún no tiene velas de prueba")
    if senal == "COMPRAR":
        accion = (f"compra con {_porcentaje(riesgo)} del saldo, stop-loss {_porcentaje(stop, 1)} y take-profit "
                  f"{_porcentaje(take, 1)}")
    elif senal == "VENDER":
        accion = "vende para proteger lo ganado"
    else:
        accion = "espera: no hay ventaja clara"
    motivo = (f"El comité da {_porcentaje(p)} de que sube la próxima vela de {nombre}; {prueba}"
              f"{'' if gana else ', así que arriesga la mitad'}. Decisión: {accion}.")
    return ConsejoPiloto(senal, p, confianza, metricas.exactitud, metricas.base, riesgo, stop, take, vol,
                         prediccion.intervalo, prediccion.tiempo_vela, precio, motivo)


class PilotoIA:
    """Une la predicción del comité con la volatilidad del mercado (cumple ``simulacion.Piloto``)."""

    def __init__(self, servicio: ServicioIA, fuente: FuenteDeMercado, simbolo: str,
                 reloj: Callable[[], int] = lambda: int(time.time() * 1000)) -> None:
        self._servicio = servicio
        self._fuente = fuente
        self._simbolo = simbolo
        self._reloj = reloj

    def aconsejar(self, intervalo: str, limites: LimitesPiloto) -> ConsejoPiloto:
        """Raises: DatosInsuficientesError, MercadoError."""
        elegido = Intervalo.desde_codigo(intervalo_ia(intervalo))
        prediccion = self._servicio.predecir(elegido)
        velas = velas_cerradas(self._fuente.obtener_velas(self._simbolo, elegido, VELAS_VOLATILIDAD + 1),
                               self._reloj())
        cierres = tuple(v.cierre for v in velas)
        precio = self._fuente.obtener_precio_actual(self._simbolo)
        return decidir(prediccion, volatilidad(cierres), precio, limites)


def consejo_para_usuario(consejo: ConsejoPiloto, tiene_btc: bool) -> tuple[str, str, str]:
    """``(accion, titulo, texto)`` del consejo para alguien según tenga BTC o no.

    ``accion`` es "COMPRAR", "VENDER", "MANTENER" o "ESPERAR" (sin nada que hacer).
    """
    nombre = NOMBRE_INTERVALO.get(consejo.intervalo, consejo.intervalo)
    prob = _porcentaje(consejo.probabilidad)
    if consejo.senal == "COMPRAR":
        if tiene_btc:
            return ("MANTENER", "La IA recomienda mantener tu BTC",
                    f"Ve {prob} de probabilidad de que suba en la próxima vela de {nombre}. Ya tienes BTC: "
                    f"si compras más, que sea poco; protégete con un stop-loss de {_porcentaje(consejo.stop_loss, 1)}.")
        return ("COMPRAR", "La IA recomienda comprar",
                f"Ve {prob} de probabilidad de que suba en la próxima vela de {nombre}. Usaría "
                f"{_porcentaje(consejo.riesgo)} de tu saldo, con stop-loss de {_porcentaje(consejo.stop_loss, 1)} y "
                f"take-profit de {_porcentaje(consejo.take_profit, 1)}.")
    if consejo.senal == "VENDER":
        if tiene_btc:
            return ("VENDER", "La IA recomienda vender",
                    f"Solo ve {prob} de probabilidad de que suba en la próxima vela de {nombre}: vender ahora "
                    "protege lo que tienes.")
        return ("ESPERAR", "La IA recomienda esperar",
                f"Solo ve {prob} de probabilidad de que suba en la próxima vela de {nombre}. No tienes BTC, así "
                "que no hay nada que proteger: mejor no comprar todavía.")
    return ("ESPERAR", "La IA recomienda esperar",
            f"Ve {prob} de probabilidad de que suba en la próxima vela de {nombre}: casi una moneda al aire. "
            "Cuando no hay ventaja clara, no operar también es una decisión.")
