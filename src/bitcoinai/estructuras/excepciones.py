"""Excepciones propias de las estructuras de datos."""


class EstructuraVaciaError(Exception):
    """Se lanza al leer o quitar un elemento de una estructura vacía.

    Por ejemplo: desencolar, desapilar, eliminar_primero o primero sobre una
    estructura sin elementos. Nunca se devuelve ``None`` en esos casos.
    """


class IndiceFueraDeRangoError(IndexError):
    """Se lanza cuando se usa un índice que no existe en la estructura."""

    def __init__(self, indice: int, tamanio: int) -> None:
        """Crea la excepción con el índice pedido y el tamaño actual.

        Complejidad: O(1).
        """
        super().__init__(f"Índice {indice} fuera de rango para tamaño {tamanio}")
        self.indice = indice
        self.tamanio = tamanio
