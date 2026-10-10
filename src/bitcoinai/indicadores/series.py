"""Operaciones comunes sobre series de puntos que usan varios indicadores."""

from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores.base import PuntoIndicador, Serie
from bitcoinai.modelo import Vela


def cierres(velas: ListaDoble[Vela] | None) -> Serie:
    """Serie de los precios de cierre: un punto (tiempo_apertura, cierre) por vela.

    Complejidad: O(n), un recorrido hacia adelante.
    """
    serie: Serie = ListaDoble()
    if velas is not None:
        for vela in velas:
            serie.agregar_final(PuntoIndicador(vela.tiempo_apertura, vela.cierre))
    return serie


def ultimos[T](lista: ListaDoble[T], n: int) -> ListaDoble[T]:
    """Los ``n`` elementos más recientes (los del final), en orden cronológico.

    Por qué se recorre hacia atrás: lo que interesa son los valores más
    recientes, que están en la cola de la lista. Empezando por la cola con el
    iterador hacia atrás (enlaces "anterior") se visitan solo esos ``n``
    elementos y se para ahí; recorriendo hacia adelante habría que pasar primero
    por todos los antiguos. Cada uno se agrega al inicio del resultado para que
    quede en orden cronológico.
    Complejidad: O(min(n, tamaño)).

    Raises:
        ValueError: si ``n`` es negativo.
    """
    if n < 0:
        raise ValueError(f"n no puede ser negativo: {n}")
    resultado: ListaDoble[T] = ListaDoble()
    for elemento in lista.iterador_atras():
        if resultado.tamanio() >= n:
            break
        resultado.agregar_inicio(elemento)
    return resultado


def ema(serie: Serie, periodo: int) -> Serie:
    """Media móvil exponencial de una serie de puntos.

    Fórmula: α = 2 / (periodo + 1); EMA₀ = media simple de los primeros
    ``periodo`` valores; EMAₜ = α·xₜ + (1 − α)·EMAₜ₋₁. El primer punto sale en la
    posición ``periodo − 1``. Con periodo 1, α = 1 y la EMA es igual a la serie.
    Complejidad: O(n), un recorrido hacia adelante.

    Raises:
        ValueError: si el periodo es menor que 1.
    """
    if periodo < 1:
        raise ValueError(f"El periodo debe ser al menos 1: {periodo}")
    alfa = 2.0 / (periodo + 1)
    resultado: Serie = ListaDoble()
    vistos = 0
    suma = 0.0
    valor_ema = 0.0
    for punto in serie:
        if vistos < periodo:
            suma += punto.valor
            vistos += 1
            if vistos == periodo:
                valor_ema = suma / periodo
                resultado.agregar_final(PuntoIndicador(punto.tiempo, valor_ema))
        else:
            valor_ema = alfa * punto.valor + (1 - alfa) * valor_ema
            resultado.agregar_final(PuntoIndicador(punto.tiempo, valor_ema))
    return resultado


def restar(a: Serie, b: Serie) -> Serie:
    """Resta dos series alineadas por posición (a − b); el tiempo de cada punto sale de ``b``.

    Complejidad: O(n), recorre las dos a la vez hacia adelante.
    """
    resultado: Serie = ListaDoble()
    for punto_a, punto_b in zip(a, b, strict=False):
        resultado.agregar_final(PuntoIndicador(punto_b.tiempo, punto_a.valor - punto_b.valor))
    return resultado


def validar_periodo(periodo: int, minimo: int = 1) -> int:
    """Devuelve el periodo si es al menos ``minimo``; si no, ``ValueError``."""
    if periodo < minimo:
        raise ValueError(f"El periodo debe ser al menos {minimo}: {periodo}")
    return periodo
