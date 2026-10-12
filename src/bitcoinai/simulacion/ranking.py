"""Liga de inversores: los k mejores por rentabilidad, con un montículo de tamaño k."""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from bitcoinai.estructuras import Lista, Monticulo

TAMANIO_POR_DEFECTO = 10

_ANIMALES = ("Halcón", "Lince", "Jaguar", "Cóndor", "Delfín", "Zorro", "Búho", "Puma", "Colibrí", "Oso",
             "Lobo", "Tigre", "Águila", "Pantera", "Toro", "Ballena")
_GEMAS = ("Dorado", "Plateado", "Esmeralda", "Rubí", "Zafiro", "Ónix", "Ámbar", "Violeta", "Perla", "Cobre",
          "Jade", "Coral")


@dataclass(frozen=True, slots=True)
class Participante:
    """Lo que la liga necesita de cada usuario: su id y cómo le va (nada personal)."""

    usuario_id: int
    valor_total: float
    rentabilidad: float


@dataclass(frozen=True, slots=True)
class Clasificado:
    """Un participante con su puesto (1 = el mejor)."""

    posicion: int
    participante: Participante


def _clave(p: Participante) -> tuple[float, int]:
    """Más rentabilidad es mejor; con empate, gana quien se registró antes (id menor)."""
    return p.rentabilidad, -p.usuario_id


def mejores(participantes: Iterable[Participante], k: int = TAMANIO_POR_DEFECTO) -> Lista[Clasificado]:
    """Los ``k`` mejores, del primero al k-ésimo.

    Un montículo de mínimos de tamaño k guarda "los k mejores vistos hasta ahora";
    su tope es el peor de ellos. Cada participante nuevo solo entra si supera ese
    tope (``reemplazar_tope``). Complejidad: O(n log k) y memoria O(k), en vez de
    ordenar a todos (O(n log n)).
    """
    if k <= 0:
        return Lista()
    monticulo: Monticulo[Participante] = Monticulo(_clave, capacidad=k)
    for p in participantes:
        if monticulo.tamanio() < k:
            monticulo.insertar(p)
        elif _clave(monticulo.ver_tope()) < _clave(p):
            monticulo.reemplazar_tope(p)
    # Salen del peor al mejor: se agregan al inicio para que la lista quede del mejor al peor.
    en_orden: Lista[Participante] = Lista()
    while not monticulo.esta_vacia():
        en_orden.agregar_inicio(monticulo.extraer())
    resultado: Lista[Clasificado] = Lista()
    for posicion, p in enumerate(en_orden, start=1):
        resultado.agregar(Clasificado(posicion, p))
    return resultado


def posicion_de(participantes: Iterable[Participante], usuario_id: int) -> Clasificado | None:
    """El puesto de un usuario: 1 + cuántos le ganan. O(n). None si no participa."""
    suyo: Participante | None = None
    mejores_que_el = 0
    todos: Lista[Participante] = Lista()
    for p in participantes:
        todos.agregar(p)
        if p.usuario_id == usuario_id:
            suyo = p
    if suyo is None:
        return None
    for p in todos:
        if _clave(suyo) < _clave(p):
            mejores_que_el += 1
    return Clasificado(mejores_que_el + 1, suyo)


def alias_publico(usuario_id: int) -> str:
    """Nombre de fantasía estable para la liga ("Halcón Dorado 07"): nunca se muestra el nombre real."""
    resumen = hashlib.sha256(f"nexabit-liga-{usuario_id}".encode()).digest()
    animal = _ANIMALES[resumen[0] % len(_ANIMALES)]
    gema = _GEMAS[resumen[1] % len(_GEMAS)]
    return f"{animal} {gema} {resumen[2] % 100:02d}"
