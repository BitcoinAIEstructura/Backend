"""Exportación del registro de órdenes a CSV.

El archivo se abre en cualquier hoja de cálculo. Dos detalles importan:

- **BOM al inicio**: sin él, Excel en Windows interpreta el archivo como latin-1 y los
  acentos («adiós», «comisión») salen rotos.
- **Neutralización de fórmulas**: un texto que empieza por ``=``, ``+``, ``-`` o ``@`` lo
  interpretaría la hoja como una fórmula (ejecución de fórmulas: un riesgo real de CSV
  injection). Se le antepone un apóstrofo para que lo trate como texto.

El entrecomillado de comas, comillas y saltos de línea lo hace el módulo ``csv``.
"""

import csv
import io

from bitcoinai.estructuras import Lista
from bitcoinai.simulacion import Orden

COLUMNAS = (
    "id",
    "tipo",
    "estado",
    "monto",
    "todo",
    "creadaEn",
    "ejecutadaEn",
    "precioEjecucion",
    "cantidadBtc",
    "comision",
    "motivo",
    "detalle",
)
"""Encabezados, en el mismo orden de los campos que escribe cada fila."""

_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")
"""Con qué empieza un texto que una hoja de cálculo intentaría evaluar."""

BOM = "\ufeff"
"""Marca de orden de bytes: le dice a Excel que el archivo es UTF-8."""


def _texto(valor: str | None) -> str:
    """Un texto listo para la hoja: vacío si falta, con apóstrofo si parece fórmula."""
    if valor is None:
        return ""
    return f"'{valor}" if valor.startswith(_INICIO_DE_FORMULA) else valor


def _numero(valor: float | None) -> str:
    """Un número sin notación científica; vacío cuando no aplica (por ejemplo, el monto de una venta de todo)."""
    return "" if valor is None else repr(float(valor))


def ordenes_a_csv(ordenes: Lista[Orden]) -> str:
    """Las órdenes en CSV, con su cabecera. Complejidad: O(n)."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\r\n")
    escritor.writerow(COLUMNAS)
    for o in ordenes:
        escritor.writerow((
            o.id,
            o.tipo.name,
            o.estado.name,
            _numero(o.monto),
            "true" if o.todo else "false",
            o.creada_en,
            "" if o.ejecutada_en is None else o.ejecutada_en,
            _numero(o.precio_ejecucion),
            _numero(o.cantidad_btc),
            _numero(o.comision),
            _texto(o.motivo),
            _texto(o.detalle),
        ))
    return salida.getvalue()


def contenido_descargable(ordenes: Lista[Orden]) -> str:
    """El CSV con el BOM delante, listo para enviar como archivo."""
    return BOM + ordenes_a_csv(ordenes)
