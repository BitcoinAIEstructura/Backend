"""Creación de indicadores por nombre a partir de parámetros en texto."""

from collections.abc import Mapping

from bitcoinai.indicadores.base import Indicador
from bitcoinai.indicadores.bollinger import BandasBollinger
from bitcoinai.indicadores.macd import Macd
from bitcoinai.indicadores.medias import Ema, Sma
from bitcoinai.indicadores.rsi import Rsi
from bitcoinai.indicadores.volatilidad import Volatilidad

NOMBRES = "sma, ema, rsi, macd, bollinger, volatilidad"
"""Nombres aceptados, para los mensajes de error."""

PERIODO_MAXIMO = 1000
"""Periodo máximo aceptado."""


def crear_indicador(nombre: str | None, parametros: Mapping[str, str] | None = None) -> Indicador:
    """Crea un indicador por nombre (sin distinguir mayúsculas), validando sus parámetros.

    | Nombre | Parámetros (por defecto) |
    | --- | --- |
    | sma, ema | periodo (20) |
    | rsi | periodo (14) |
    | macd | rapido (12), lento (26), senal (9) |
    | bollinger | periodo (20), desviaciones (2) |
    | volatilidad | periodo (20) |

    Todos los periodos deben estar entre 2 y 1000. Un periodo mayor que la
    cantidad de velas no es un error: el indicador devuelve una serie vacía.
    Los parámetros que el indicador no usa se ignoran.

    Raises:
        ValueError: con un mensaje claro si el nombre o algún parámetro es inválido.
    """
    p = parametros or {}
    clave = (nombre or "").strip().lower()
    if clave == "sma":
        return Sma(_periodo(p, "periodo", 20))
    if clave == "ema":
        return Ema(_periodo(p, "periodo", 20))
    if clave == "rsi":
        return Rsi(_periodo(p, "periodo", 14))
    if clave == "macd":
        rapido = _periodo(p, "rapido", 12)
        lento = _periodo(p, "lento", 26)
        senal = _periodo(p, "senal", 9)
        if lento <= rapido:
            raise ValueError(f"Parámetro 'lento' ({lento}) debe ser mayor que 'rapido' ({rapido})")
        return Macd(rapido, lento, senal)
    if clave == "bollinger":
        return BandasBollinger(_periodo(p, "periodo", 20), _desviaciones(p))
    if clave == "volatilidad":
        return Volatilidad(_periodo(p, "periodo", 20))
    if clave == "":
        raise ValueError(f"Falta el parámetro 'indicador'. Valores permitidos: {NOMBRES}")
    raise ValueError(f"Indicador desconocido: '{nombre}'. Valores permitidos: {NOMBRES}")


def _periodo(parametros: Mapping[str, str], nombre: str, por_defecto: int) -> int:
    texto = parametros.get(nombre)
    if texto is None or not texto.strip():
        return por_defecto
    try:
        valor = int(texto.strip())
    except ValueError:
        valor = 0
    if not 2 <= valor <= PERIODO_MAXIMO:
        raise ValueError(f"Parámetro '{nombre}' inválido: '{texto}'. "
                         f"Debe ser un número entero entre 2 y {PERIODO_MAXIMO}")
    return valor


def _desviaciones(parametros: Mapping[str, str]) -> float:
    texto = parametros.get("desviaciones")
    if texto is None or not texto.strip():
        return 2.0
    try:
        valor = float(texto.strip())
    except ValueError:
        valor = 0.0
    if not 0 < valor <= 10:
        raise ValueError(f"Parámetro 'desviaciones' inválido: '{texto}'. "
                         "Debe ser un número mayor que 0 y como máximo 10")
    return valor
