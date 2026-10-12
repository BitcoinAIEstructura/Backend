"""Los últimos precios vistos, en una cola circular (memoria fija)."""

import threading

from bitcoinai.estructuras import ColaCircular, Lista

CAPACIDAD_POR_DEFECTO = 120
"""120 precios: con uno cada 5 s son los últimos 10 minutos."""

SEPARACION_MINIMA_MS = 2000
"""Si llegan dos precios con menos de 2 s entre sí, se guarda solo el primero."""


class PreciosRecientes:
    """Guarda ``(momento, precio)`` de los últimos precios que pasaron por el servidor.

    Una ``ColaCircular`` de capacidad fija: al llenarse, cada precio nuevo pisa al
    más viejo en O(1), así la memoria no crece por más que el servidor lleve días
    encendido. La alimentan el tiempo real (cada 5 s) y ``GET /api/precio``.
    Un candado la protege: escriben varios hilos.
    """

    def __init__(self, capacidad: int = CAPACIDAD_POR_DEFECTO,
                 separacion_minima_ms: int = SEPARACION_MINIMA_MS) -> None:
        self._precios: ColaCircular[tuple[int, float]] = ColaCircular(capacidad)
        self._separacion = separacion_minima_ms
        self._candado = threading.Lock()

    def registrar(self, momento_ms: int, precio: float) -> bool:
        """Anota un precio, salvo que sea muy seguido al anterior o más viejo que él. O(1).

        Returns:
            True si se guardó.
        """
        with self._candado:
            if not self._precios.esta_vacia():
                ultimo_momento, _ = self._precios.ver_final()
                if momento_ms - ultimo_momento < self._separacion:
                    return False
            self._precios.agregar((momento_ms, precio))
            return True

    def instantanea(self) -> Lista[tuple[int, float]]:
        """Copia de los precios guardados, del más viejo al más nuevo. O(n)."""
        copia: Lista[tuple[int, float]] = Lista()
        with self._candado:
            for par in self._precios:
                copia.agregar(par)
        return copia

    def capacidad(self) -> int:
        """Cuántos precios caben. O(1)."""
        return self._precios.capacidad()

    def estado_del_anillo(self) -> tuple[int, int, Lista[float | None]]:
        """Frente, tamaño y precio de cada casilla (``None`` si está vacía), para dibujar el anillo. O(capacidad)."""
        casillas: Lista[float | None] = Lista()
        with self._candado:
            for casilla in self._precios.casillas():
                casillas.agregar(None if casilla is None else casilla[1])
            return self._precios.indice_frente(), self._precios.tamanio(), casillas
