"""Creación de estrategias por nombre y candidatos para la validación."""

from collections.abc import Mapping

from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estrategia.combinada import Componente, EstrategiaCombinada
from bitcoinai.estrategia.cruce import CruceDeMedias
from bitcoinai.estrategia.macd import EstrategiaMacd
from bitcoinai.estrategia.rsi import EstrategiaRsi
from bitcoinai.estructuras import Lista

NOMBRES = "cruce, rsi, macd, combinada"
"""Nombres aceptados, para los mensajes de error."""


def crear_estrategia(nombre: str | None, parametros: Mapping[str, str] | None = None) -> Estrategia:
    """Crea una estrategia por nombre (sin distinguir mayúsculas), validando sus parámetros.

    | Nombre | Parámetros (por defecto) |
    | --- | --- |
    | cruce | corta (20), larga (50) |
    | rsi | periodo (14), sobreventa (30), sobrecompra (70) |
    | macd | rapido (12), lento (26), senal (9) |
    | combinada | pesoCruce, pesoRsi, pesoMacd (1 cada uno) y los de las tres anteriores |

    Los parámetros que no use se ignoran.

    Raises:
        ValueError: con un mensaje claro si el nombre o algún parámetro es inválido.
    """
    p = parametros or {}
    clave = (nombre or "").strip().lower()
    if clave == "cruce":
        return _cruce(p)
    if clave == "rsi":
        return _rsi(p)
    if clave == "macd":
        return _macd(p)
    if clave == "combinada":
        componentes = (Componente(_cruce(p), _peso(p, "pesoCruce")), Componente(_rsi(p), _peso(p, "pesoRsi")),
                       Componente(_macd(p), _peso(p, "pesoMacd")))
        try:
            return EstrategiaCombinada(componentes)
        except ValueError:
            raise ValueError("Al menos uno de pesoCruce, pesoRsi o pesoMacd debe ser mayor que 0") from None
    if clave == "":
        raise ValueError(f"Falta el parámetro 'estrategia'. Valores permitidos: {NOMBRES}")
    raise ValueError(f"Estrategia desconocida: '{nombre}'. Valores permitidos: {NOMBRES}")


def candidatos(nombre: str) -> Lista[Estrategia]:
    """Combinaciones de parámetros que prueba la validación entrenamiento/prueba.

    Raises:
        ValueError: si el nombre no existe.
    """
    clave = nombre.strip().lower()
    lista: Lista[Estrategia] = Lista()
    if clave == "cruce":
        for corta in (5, 10, 20):
            for larga in (30, 50, 100):
                lista.agregar(CruceDeMedias(corta, larga))
    elif clave == "rsi":
        for periodo in (7, 14, 21):
            for nivel in (30, 25, 20):
                lista.agregar(EstrategiaRsi(periodo, nivel, 100 - nivel))
    elif clave == "macd":
        for rapido, lento, senal in ((12, 26, 9), (8, 17, 9), (5, 35, 5)):
            lista.agregar(EstrategiaMacd(rapido, lento, senal))
    elif clave == "combinada":
        for pesos in ((1, 1, 1), (2, 1, 1), (1, 2, 1), (1, 1, 2)):
            lista.agregar(EstrategiaCombinada.con_pesos(*pesos))
    else:
        raise ValueError(f"Estrategia desconocida: '{nombre}'. Valores permitidos: {NOMBRES}")
    return lista


def _cruce(p: Mapping[str, str]) -> CruceDeMedias:
    corta = _entero(p, "corta", 20, 2, 500)
    larga = _entero(p, "larga", 50, 3, 1000)
    if larga <= corta:
        raise ValueError(f"Parámetro 'larga' ({larga}) debe ser mayor que 'corta' ({corta})")
    return CruceDeMedias(corta, larga)


def _rsi(p: Mapping[str, str]) -> EstrategiaRsi:
    return EstrategiaRsi(_entero(p, "periodo", 14, 2, 500), _entero(p, "sobreventa", 30, 1, 49),
                         _entero(p, "sobrecompra", 70, 51, 99))


def _macd(p: Mapping[str, str]) -> EstrategiaMacd:
    rapido = _entero(p, "rapido", 12, 2, 500)
    lento = _entero(p, "lento", 26, 3, 1000)
    senal = _entero(p, "senal", 9, 2, 500)
    if lento <= rapido:
        raise ValueError(f"Parámetro 'lento' ({lento}) debe ser mayor que 'rapido' ({rapido})")
    return EstrategiaMacd(rapido, lento, senal)


def _entero(p: Mapping[str, str], nombre: str, por_defecto: int, minimo: int, maximo: int) -> int:
    texto = p.get(nombre)
    if texto is None or not texto.strip():
        return por_defecto
    try:
        valor = int(texto.strip())
    except ValueError:
        valor = minimo - 1
    if not minimo <= valor <= maximo:
        raise ValueError(f"Parámetro '{nombre}' inválido: '{texto}'. "
                         f"Debe ser un número entero entre {minimo} y {maximo}")
    return valor


def _peso(p: Mapping[str, str], nombre: str) -> float:
    texto = p.get(nombre)
    if texto is None or not texto.strip():
        return 1.0
    try:
        valor = float(texto.strip())
    except ValueError:
        valor = -1.0
    if not 0 <= valor <= 10:
        raise ValueError(f"Parámetro '{nombre}' inválido: '{texto}'. Debe ser un número entre 0 y 10")
    return valor
