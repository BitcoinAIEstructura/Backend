"""Guardia: las estructuras están hechas a mano, sin colecciones de Python por dentro.

Revisa el código fuente (con el árbol sintáctico, no con texto) y falla si
aparece una lista, un diccionario, un conjunto, una comprensión o el uso de
list, dict, set, deque, queue o heapq.
"""

import ast
from pathlib import Path

import bitcoinai.estructuras

CARPETA = Path(bitcoinai.estructuras.__file__).parent
NOMBRES_PROHIBIDOS = {"list", "dict", "set", "deque", "Queue", "SimpleQueue", "LifoQueue", "heappush", "heappop"}
MODULOS_PROHIBIDOS = {"collections", "queue", "heapq"}


def nodos_de_anotaciones(arbol: ast.AST) -> set[int]:
    """Ids de los nodos que están dentro de anotaciones de tipo.

    En ``Callable[[T], bool]`` los corchetes internos son sintaxis de tipos, no
    una lista que se cree al ejecutar, así que no cuentan.
    """
    anotaciones: tuple[ast.expr, ...] = ()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
            argumentos = nodo.args.posonlyargs + nodo.args.args + nodo.args.kwonlyargs
            anotaciones += tuple(a.annotation for a in argumentos if a.annotation is not None)
            if nodo.returns is not None:
                anotaciones += (nodo.returns,)
        elif isinstance(nodo, ast.AnnAssign):
            anotaciones += (nodo.annotation,)
    return {id(n) for anotacion in anotaciones for n in ast.walk(anotacion)}


def problemas_en(archivo: Path) -> tuple[str, ...]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    ignorar = nodos_de_anotaciones(arbol)
    encontrados: tuple[str, ...] = ()
    for nodo in ast.walk(arbol):
        if id(nodo) in ignorar:
            continue
        lugar = f"{archivo.name}:{getattr(nodo, 'lineno', '?')}"
        if isinstance(nodo, ast.List | ast.Dict | ast.Set | ast.ListComp | ast.DictComp | ast.SetComp):
            encontrados += (f"{lugar} usa {type(nodo).__name__}",)
        elif isinstance(nodo, ast.Name) and nodo.id in NOMBRES_PROHIBIDOS:
            encontrados += (f"{lugar} usa {nodo.id}",)
        elif isinstance(nodo, ast.Import | ast.ImportFrom):
            modulos = (nodo.module or "",) if isinstance(nodo, ast.ImportFrom) else tuple(a.name for a in nodo.names)
            for modulo in modulos:
                if modulo.split(".")[0] in MODULOS_PROHIBIDOS and modulo != "collections.abc":
                    encontrados += (f"{lugar} importa {modulo}",)
    return encontrados


def test_las_estructuras_no_usan_colecciones_de_python() -> None:
    archivos = tuple(CARPETA.glob("*.py"))
    assert len(archivos) >= 7
    problemas: tuple[str, ...] = ()
    for archivo in archivos:
        problemas += problemas_en(archivo)
    assert problemas == (), "\n".join(problemas)


def test_la_guardia_detecta_una_lista(tmp_path: Path) -> None:
    trampa = tmp_path / "trampa.py"
    trampa.write_text("from collections import deque\nx = [1, 2]\ny = list()\n", encoding="utf-8")
    assert len(problemas_en(trampa)) == 3


def test_la_guardia_ignora_las_anotaciones_de_tipo(tmp_path: Path) -> None:
    tipos = tmp_path / "tipos.py"
    tipos.write_text("def f(g: Callable[[int], bool]) -> list[int]:\n    return g\n", encoding="utf-8")
    assert problemas_en(tipos) == ()
