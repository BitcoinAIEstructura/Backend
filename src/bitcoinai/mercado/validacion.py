"""Validación de series de velas y filtro de la vela en curso."""

import math

from bitcoinai.estructuras import ListaDoble
from bitcoinai.mercado.errores import MercadoError
from bitcoinai.modelo import Vela


def validar_velas(velas: ListaDoble[Vela]) -> None:
    """Comprueba que una serie de velas sea coherente antes de usarla.

    Reglas:
        - ordenadas por tiempo de apertura, de la más antigua a la más reciente, sin duplicados;
        - precios positivos y finitos; volumen no negativo;
        - máximo >= mínimo, y apertura y cierre dentro de ese rango;
        - tiempo de cierre no anterior al de apertura.

    Complejidad: O(n), un solo recorrido hacia adelante.

    Raises:
        MercadoError: con la posición y el motivo de la primera vela inválida.
    """
    anterior: Vela | None = None
    for indice, vela in enumerate(velas):
        _validar_vela(vela, indice)
        if anterior is not None:
            if vela.tiempo_apertura == anterior.tiempo_apertura:
                raise _invalida(indice, f"vela duplicada (tiempo_apertura {vela.tiempo_apertura})")
            if vela.tiempo_apertura < anterior.tiempo_apertura:
                raise _invalida(
                    indice,
                    f"velas desordenadas (tiempo_apertura {vela.tiempo_apertura} "
                    f"es anterior a {anterior.tiempo_apertura})",
                )
        anterior = vela


def velas_cerradas(velas: ListaDoble[Vela], ahora: int) -> ListaDoble[Vela]:
    """Quita del final las velas que todavía no cerraron (la del periodo en curso).

    Sus valores aún cambian, y una señal calculada con ella podría desaparecer.
    Modifica la lista recibida y la devuelve.
    Complejidad: O(k), con k velas quitadas (normalmente 0 o 1); cada
    ``eliminar_ultimo()`` es O(1).
    """
    while not velas.esta_vacia() and velas.ultimo().tiempo_cierre >= ahora:
        velas.eliminar_ultimo()
    return velas


def _validar_vela(vela: Vela | None, indice: int) -> None:
    if vela is None:
        raise _invalida(indice, "la vela es nula")
    if not all(_positivo(p) for p in (vela.apertura, vela.maximo, vela.minimo, vela.cierre)):
        raise _invalida(indice, "los precios deben ser positivos")
    if vela.maximo < vela.minimo:
        raise _invalida(indice, "el máximo es menor que el mínimo")
    if vela.maximo < max(vela.apertura, vela.cierre) or vela.minimo > min(vela.apertura, vela.cierre):
        raise _invalida(indice, "la apertura o el cierre están fuera del rango mínimo-máximo")
    if not (vela.volumen >= 0 and math.isfinite(vela.volumen)):
        raise _invalida(indice, "el volumen debe ser cero o positivo")
    if vela.tiempo_cierre < vela.tiempo_apertura:
        raise _invalida(indice, "el tiempo de cierre es anterior al de apertura")


def _positivo(valor: float) -> bool:
    return valor > 0 and math.isfinite(valor)


def _invalida(indice: int, motivo: str) -> MercadoError:
    return MercadoError(f"Vela inválida en la posición {indice}: {motivo}")
