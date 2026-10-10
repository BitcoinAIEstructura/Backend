"""Límite de intentos por clave (correo, IP…) con ventana deslizante.

Frena la fuerza bruta: por ejemplo, 5 contraseñas equivocadas para un correo en
15 minutos bloquean ese correo hasta que el intento más viejo salga de la ventana.

**Uso de la cola:** por cada clave se guarda una ``Cola`` con los momentos de los
intentos, del más viejo (frente) al más nuevo (final). Al consultar, se
desencolan los que ya salieron de la ventana. Cada intento entra y sale una sola
vez, así que el costo amortizado es O(1) por intento, y la memoria por clave
nunca pasa de ``maximo`` elementos.
"""

import threading
import time
from collections.abc import Callable

from bitcoinai.estructuras import Cola


class LimitadorIntentos:
    """Permite como máximo ``maximo`` intentos por clave dentro de ``ventana`` segundos."""

    def __init__(self, maximo: int, ventana: float, reloj: Callable[[], float] = time.monotonic) -> None:
        """Raises: ValueError si el máximo o la ventana no son positivos."""
        if maximo < 1 or ventana <= 0:
            raise ValueError("El máximo y la ventana deben ser positivos")
        self.maximo = maximo
        self.ventana = ventana
        self._reloj = reloj
        self._intentos: dict[str, Cola[float]] = {}
        self._candado = threading.Lock()

    def _vigentes(self, clave: str, ahora: float) -> Cola[float] | None:
        """La cola de la clave sin los intentos vencidos. Se llama con el candado tomado."""
        cola = self._intentos.get(clave)
        if cola is None:
            return None
        while not cola.esta_vacia() and cola.ver_frente() <= ahora - self.ventana:
            cola.desencolar()
        if cola.esta_vacia():
            del self._intentos[clave]
            return None
        return cola

    def registrar(self, clave: str) -> None:
        """Anota un intento. Complejidad: O(1) amortizado."""
        with self._candado:
            ahora = self._reloj()
            cola = self._vigentes(clave, ahora)
            if cola is None:
                cola = Cola()
                self._intentos[clave] = cola
            cola.encolar(ahora)
            while cola.tamanio() > self.maximo:  # no hace falta recordar más de "maximo"
                cola.desencolar()

    def permitido(self, clave: str) -> bool:
        """True si todavía no se llegó al máximo dentro de la ventana."""
        return self.espera(clave) == 0

    def espera(self, clave: str) -> float:
        """Segundos que faltan para poder intentar de nuevo (0 si ya se puede)."""
        with self._candado:
            ahora = self._reloj()
            cola = self._vigentes(clave, ahora)
            if cola is None or cola.tamanio() < self.maximo:
                return 0.0
            return max(0.0, cola.ver_frente() + self.ventana - ahora)

    def reiniciar(self, clave: str) -> None:
        """Olvida los intentos de una clave (por ejemplo, tras iniciar sesión bien)."""
        with self._candado:
            self._intentos.pop(clave, None)

    def cantidad_claves(self) -> int:
        with self._candado:
            return len(self._intentos)
