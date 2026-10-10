"""Caché en memoria para cualquier fuente de mercado."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from bitcoinai.estructuras import ListaDoble
from bitcoinai.mercado.fuente import FuenteDeMercado
from bitcoinai.modelo import Intervalo, Vela


@dataclass(frozen=True, slots=True)
class _Entrada:
    valor: object
    expira_en: float


class CacheMercado:
    """Envuelve una ``FuenteDeMercado`` y guarda sus respuestas durante un tiempo (TTL).

    Cada combinación de símbolo, intervalo y cantidad se guarda por separado,
    igual que el precio de cada símbolo. Los errores no se guardan. Devuelve
    copias de las velas, para que quien las reciba pueda modificarlas sin dañar
    la caché. Si dos hilos piden lo mismo a la vez, puede que ambos consulten la
    fuente, lo cual es aceptable.
    """

    def __init__(
        self,
        fuente: FuenteDeMercado,
        ttl_segundos: float,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        """Crea la caché.

        Args:
            fuente: fuente real a la que se consulta cuando no hay dato vigente.
            ttl_segundos: segundos que un dato es válido (0 desactiva la caché).
            reloj: segundos actuales; en pruebas, uno controlable.

        Raises:
            ValueError: si el TTL es negativo.
        """
        if ttl_segundos < 0:
            raise ValueError("El TTL no puede ser negativo")
        self._fuente = fuente
        self._ttl = ttl_segundos
        self._reloj = reloj
        self._entradas: dict[str, _Entrada] = {}

    def obtener_velas(self, simbolo: str, intervalo: Intervalo, cantidad: int) -> ListaDoble[Vela]:
        """Velas desde la caché si siguen vigentes; si no, desde la fuente.

        Complejidad: O(1) para consultar la caché más O(n) para copiar las n velas.
        """
        clave = f"velas|{simbolo}|{intervalo.codigo}|{cantidad}"
        velas = self._obtener(clave, lambda: self._fuente.obtener_velas(simbolo, intervalo, cantidad))
        return _copiar(cast(ListaDoble[Vela], velas))

    def obtener_precio_actual(self, simbolo: str) -> float:
        """Precio desde la caché si sigue vigente; si no, desde la fuente. Complejidad: O(1)."""
        return cast(float, self._obtener(f"precio|{simbolo}", lambda: self._fuente.obtener_precio_actual(simbolo)))

    def _obtener(self, clave: str, cargar: Callable[[], object]) -> object:
        ahora = self._reloj()
        entrada = self._entradas.get(clave)
        if entrada is not None and ahora < entrada.expira_en:
            return entrada.valor
        valor = cargar()  # si falla, la excepción sale sin guardar nada
        self._entradas[clave] = _Entrada(valor, ahora + self._ttl)
        return valor


def _copiar(original: ListaDoble[Vela]) -> ListaDoble[Vela]:
    copia: ListaDoble[Vela] = ListaDoble()
    for vela in original:
        copia.agregar_final(vela)
    return copia
