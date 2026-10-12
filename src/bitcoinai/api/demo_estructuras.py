"""Demostración paso a paso de las estructuras para la pantalla "Cómo funciona".

Corre el código real de ``bitcoinai.estructuras`` sobre una estructura nueva y,
después de cada operación, toma una foto de cómo quedó (para dibujarla). No guarda
nada entre peticiones. No depende de FastAPI: recibe y devuelve datos simples.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from bitcoinai.busqueda import normalizar
from bitcoinai.estructuras import (
    ArbolAVL,
    Cola,
    ColaCircular,
    EstructuraVaciaError,
    Monticulo,
    NodoAVL,
    NodoTrie,
    Pila,
    TablaHash,
    Trie,
)

MAXIMO_OPERACIONES = 30
VALOR_MINIMO, VALOR_MAXIMO = -9999, 99999
LARGO_MAXIMO_PALABRA = 12
CAPACIDAD_COLA_CIRCULAR = 8
CAPACIDAD_TABLA = 4  # chica a propósito: así se ve crecer
NIVELES_MAXIMOS_DIBUJO = 7


class DemoInvalidaError(ValueError):
    """La petición de demostración no se puede correr (el mensaje dice por qué)."""


@dataclass(frozen=True, slots=True)
class Operacion:
    nombre: str
    valor: int | str | None = None


OPERACIONES: dict[str, tuple[str, ...]] = {
    "cola": ("encolar", "desencolar"),
    "pila": ("apilar", "desapilar"),
    "monticulo": ("insertar", "extraer"),
    "avl": ("insertar", "eliminar", "buscar"),
    "tabla-hash": ("poner", "eliminar", "buscar"),
    "cola-circular": ("agregar", "desencolar"),
    "trie": ("insertar", "eliminar", "buscar"),
}

SIN_VALOR = ("desencolar", "desapilar", "extraer")

COMPLEJIDAD: dict[tuple[str, str], str] = {
    ("cola", "encolar"): "O(1)", ("cola", "desencolar"): "O(1)",
    ("pila", "apilar"): "O(1)", ("pila", "desapilar"): "O(1)",
    ("monticulo", "insertar"): "O(log n)", ("monticulo", "extraer"): "O(log n)",
    ("avl", "insertar"): "O(log n)", ("avl", "eliminar"): "O(log n)", ("avl", "buscar"): "O(log n)",
    ("tabla-hash", "poner"): "O(1) promedio", ("tabla-hash", "eliminar"): "O(1) promedio",
    ("tabla-hash", "buscar"): "O(1) promedio",
    ("cola-circular", "agregar"): "O(1)", ("cola-circular", "desencolar"): "O(1)",
    ("trie", "insertar"): "O(m)", ("trie", "eliminar"): "O(m)", ("trie", "buscar"): "O(m)",
}


# ---------- validación ----------


def _validar(estructura: str, operaciones: Iterable[Operacion]) -> tuple[Operacion, ...]:
    if estructura not in OPERACIONES:
        raise DemoInvalidaError(f"Estructura desconocida: '{estructura}'. Opciones: {', '.join(OPERACIONES)}")
    validas: tuple[Operacion, ...] = ()
    for op in operaciones:
        if len(validas) >= MAXIMO_OPERACIONES:
            raise DemoInvalidaError(f"Demasiadas operaciones (máximo {MAXIMO_OPERACIONES})")
        if op.nombre not in OPERACIONES[estructura]:
            raise DemoInvalidaError(f"Operación '{op.nombre}' no válida para {estructura}. "
                                    f"Opciones: {', '.join(OPERACIONES[estructura])}")
        validas += (Operacion(op.nombre, _valor(estructura, op)),)
    return validas


def _valor(estructura: str, op: Operacion) -> int | str | None:
    if op.nombre in SIN_VALOR:
        return None
    if estructura == "trie":
        if not isinstance(op.valor, str):
            raise DemoInvalidaError("En el trie los valores son palabras")
        palabra = normalizar(op.valor.strip())
        if not (1 <= len(palabra) <= LARGO_MAXIMO_PALABRA and palabra.isalpha()):
            raise DemoInvalidaError(f"Palabra inválida: '{op.valor}'. Solo letras, de 1 a {LARGO_MAXIMO_PALABRA}")
        return palabra
    if isinstance(op.valor, bool) or not isinstance(op.valor, int):
        raise DemoInvalidaError(f"La operación '{op.nombre}' necesita un número entero")
    if not VALOR_MINIMO <= op.valor <= VALOR_MAXIMO:
        raise DemoInvalidaError(f"Los números van de {VALOR_MINIMO} a {VALOR_MAXIMO}")
    return op.valor


# ---------- fotos ----------


def _foto_cola(cola: Cola[int]) -> dict[str, Any]:
    """Se lee rotando: desencolar y volver a encolar n veces la deja igual. O(n)."""
    elementos = []
    for _ in range(cola.tamanio()):
        x = cola.desencolar()
        cola.encolar(x)
        elementos.append(x)
    return {"elementos": elementos}


def _foto_pila(pila: Pila[int]) -> dict[str, Any]:
    """Del tope al fondo, con una pila auxiliar para devolverlos. O(n)."""
    auxiliar: Pila[int] = Pila()
    elementos = []
    while not pila.esta_vacia():
        x = pila.desapilar()
        elementos.append(x)
        auxiliar.apilar(x)
    while not auxiliar.esta_vacia():
        pila.apilar(auxiliar.desapilar())
    return {"elementos": elementos}


def _foto_monticulo(m: Monticulo[int]) -> dict[str, Any]:
    return {"arreglo": list(m.en_orden_de_arreglo()), "capacidad": m.capacidad()}


def _nodo_avl(nodo: NodoAVL[int, None] | None, nivel: int) -> dict[str, Any] | None:
    if nodo is None or nivel >= NIVELES_MAXIMOS_DIBUJO:
        return None
    return {"clave": nodo.clave, "altura": nodo.altura,
            "izquierdo": _nodo_avl(nodo.izquierdo, nivel + 1), "derecho": _nodo_avl(nodo.derecho, nivel + 1)}


def _foto_avl(arbol: ArbolAVL[int, None]) -> dict[str, Any]:
    return {"raiz": _nodo_avl(arbol.raiz(), 0), "altura": arbol.altura(), "tamanio": arbol.tamanio()}


def _foto_tabla(tabla: TablaHash[int, None]) -> dict[str, Any]:
    return {"capacidad": tabla.capacidad(), "factorCarga": tabla.factor_de_carga(),
            "cubetas": [list(cubeta) for cubeta in tabla.claves_por_cubeta()]}


def _foto_circular(cola: ColaCircular[int]) -> dict[str, Any]:
    return {"capacidad": cola.capacidad(), "frente": cola.indice_frente(), "tamanio": cola.tamanio(),
            "casillas": list(cola.casillas())}


def _nodo_trie(nodo: NodoTrie[None]) -> dict[str, Any]:
    return {"letra": nodo.letra, "fin": nodo.tiene_valor, "hijos": [_nodo_trie(h) for h in nodo.hijos()]}


def _foto_trie(trie: Trie[None]) -> dict[str, Any]:
    return {"raiz": _nodo_trie(trie.raiz()), "palabras": trie.tamanio(), "nodos": trie.cantidad_nodos()}


# ---------- ejecución ----------


def ejecutar(estructura: str, operaciones: Iterable[Operacion]) -> list[dict[str, Any]]:
    """Corre las operaciones en orden y devuelve un paso por cada una.

    Cada paso: ``{"operacion", "valor", "resultado", "descripcion", "complejidad", "estado"}``.

    Raises:
        DemoInvalidaError: estructura, operación o valor inválidos.
    """
    validas = _validar(estructura, operaciones)
    hacer, fotografiar = _CORREDORES[estructura]()
    pasos = []
    for op in validas:
        try:
            resultado, descripcion = hacer(op)
        except EstructuraVaciaError:
            resultado, descripcion = None, "Está vacía: no hay nada que sacar."
        pasos.append({
            "operacion": op.nombre,
            "valor": op.valor,
            "resultado": resultado,
            "descripcion": descripcion,
            "complejidad": COMPLEJIDAD[(estructura, op.nombre)],
            "estado": fotografiar(),
        })
    return pasos


type Corredor = tuple[Callable[[Operacion], tuple[Any, str]], Callable[[], dict[str, Any]]]


def _cola() -> Corredor:
    cola: Cola[int] = Cola()

    def hacer(op: Operacion) -> tuple[Any, str]:
        if op.nombre == "encolar":
            cola.encolar(int(op.valor))  # type: ignore[arg-type]
            return None, f"{op.valor} entra por el final."
        x = cola.desencolar()
        return x, f"Sale {x}: el que llegó primero."
    return hacer, lambda: _foto_cola(cola)


def _pila() -> Corredor:
    pila: Pila[int] = Pila()

    def hacer(op: Operacion) -> tuple[Any, str]:
        if op.nombre == "apilar":
            pila.apilar(int(op.valor))  # type: ignore[arg-type]
            return None, f"{op.valor} queda en el tope."
        x = pila.desapilar()
        return x, f"Sale {x}: el último que entró."
    return hacer, lambda: _foto_pila(pila)


def _monticulo() -> Corredor:
    m: Monticulo[int] = Monticulo(lambda x: x, capacidad=4)

    def hacer(op: Operacion) -> tuple[Any, str]:
        if op.nombre == "insertar":
            capacidad = m.capacidad()
            m.insertar(int(op.valor))  # type: ignore[arg-type]
            subio = m.intercambios_ultima_operacion()
            extra = f" El arreglo se llenó y creció a {m.capacidad()} casillas." if m.capacidad() > capacidad else ""
            return None, (f"{op.valor} entra al final y sube {subio} nivel{'es' if subio != 1 else ''} "
                          f"hasta quedar debajo de uno menor.{extra}")
        x = m.extraer()
        bajo = m.intercambios_ultima_operacion()
        return x, f"Sale {x}, el menor. El último pasa a la raíz y baja {bajo} nivel{'es' if bajo != 1 else ''}."
    return hacer, lambda: _foto_monticulo(m)


def _avl() -> Corredor:
    arbol: ArbolAVL[int, None] = ArbolAVL()

    def hacer(op: Operacion) -> tuple[Any, str]:
        clave = int(op.valor)  # type: ignore[arg-type]
        if op.nombre == "buscar":
            esta = arbol.contiene(clave)
            return esta, f"{clave} {'está' if esta else 'no está'}. Se bajó por una sola rama."
        if op.nombre == "insertar":
            nueva = arbol.insertar(clave, None)
            texto = f"{clave} entra." if nueva else f"{clave} ya estaba."
        else:
            quitada = arbol.eliminar(clave)
            texto = f"{clave} sale." if quitada else f"{clave} no estaba."
        rotaciones = tuple(arbol.rotaciones_ultima_operacion())
        texto += " " + (". ".join(rotaciones) + "." if rotaciones else "Sigue balanceado: sin rotaciones.")
        return None, texto
    return hacer, lambda: _foto_avl(arbol)


def _tabla() -> Corredor:
    tabla: TablaHash[int, None] = TablaHash(CAPACIDAD_TABLA)

    def hacer(op: Operacion) -> tuple[Any, str]:
        clave = int(op.valor)  # type: ignore[arg-type]
        if op.nombre == "buscar":
            esta = tabla.contiene(clave)
            return esta, f"{clave} {'está' if esta else 'no está'}: se revisó solo su cubeta."
        if op.nombre == "eliminar":
            quitada = tabla.eliminar(clave)
            return quitada, f"{clave} {'sale de su cadena' if quitada else 'no estaba'}."
        capacidad = tabla.capacidad()
        nueva = tabla.poner(clave, None)
        if tabla.capacidad() > capacidad:
            return nueva, (f"{clave} haría pasar el factor de carga de 0,75: la tabla creció a "
                           f"{tabla.capacidad()} cubetas y reubicó todo (rehash).")
        return nueva, f"{clave} va a su cubeta según su hash." if nueva else f"{clave} ya estaba."
    return hacer, lambda: _foto_tabla(tabla)


def _circular() -> Corredor:
    cola: ColaCircular[int] = ColaCircular(CAPACIDAD_COLA_CIRCULAR)

    def hacer(op: Operacion) -> tuple[Any, str]:
        if op.nombre == "agregar":
            pisado = cola.agregar(int(op.valor))  # type: ignore[arg-type]
            if pisado is not None:
                return pisado, f"Estaba llena: {op.valor} pisa a {pisado}, el más viejo, y el frente avanza."
            return None, f"{op.valor} entra en la casilla siguiente."
        x = cola.desencolar()
        return x, f"Sale {x}, el más viejo; su casilla queda libre."
    return hacer, lambda: _foto_circular(cola)


def _trie() -> Corredor:
    trie: Trie[None] = Trie()

    def hacer(op: Operacion) -> tuple[Any, str]:
        palabra = str(op.valor)
        if op.nombre == "buscar":
            esta = trie.contiene(palabra)
            sugerencias = ", ".join(p for p, _ in trie.con_prefijo(palabra, 5))
            texto = f"'{palabra}' {'está' if esta else 'no está'}."
            return esta, texto + (f" Empiezan así: {sugerencias}." if sugerencias else "")
        nodos = trie.cantidad_nodos()
        if op.nombre == "insertar":
            nueva = trie.insertar(palabra, None)
            nuevos = trie.cantidad_nodos() - nodos
            return nueva, (f"'{palabra}' entra con {nuevos} nodo{'s' if nuevos != 1 else ''} nuevo"
                           f"{'s' if nuevos != 1 else ''}; reutiliza {len(palabra) - nuevos} del prefijo.")
        quitada = trie.eliminar(palabra)
        return quitada, (f"'{palabra}' sale y se podan {nodos - trie.cantidad_nodos()} nodos." if quitada
                         else f"'{palabra}' no estaba.")
    return hacer, lambda: _foto_trie(trie)


_CORREDORES: dict[str, Callable[[], Corredor]] = {
    "cola": _cola, "pila": _pila, "monticulo": _monticulo, "avl": _avl,
    "tabla-hash": _tabla, "cola-circular": _circular, "trie": _trie,
}
