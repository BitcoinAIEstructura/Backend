"""Utilidades compartidas por las estrategias."""

from bitcoinai.estrategia.modelo import Decision, Senal
from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import Serie
from bitcoinai.modelo import Vela

CONFIANZA_NEUTRA = 0.25
"""Confianza de un MANTENER cuando no pasa nada.

Es baja a propósito: en la estrategia combinada, una señal clara (confianza 0,6
o más) de una sola estrategia debe poder ganarle a dos "no pasa nada".
"""

_TOLERANCIA_RELATIVA = 1e-9
"""Por debajo de esta fracción del precio, una diferencia se considera cero (evita cruces por ruido numérico)."""


def confianza_por_distancia(distancia_relativa: float) -> float:
    """0,6 como base, más hasta 0,4 según la distancia relativa al precio (0,4 % o más da 1)."""
    return 0.6 + min(0.4, abs(distancia_relativa) * 100)


def signo(valor: float, escala: float) -> int:
    """Signo de un valor (-1, 0 o 1), tratando como 0 lo despreciable frente a la escala (el precio)."""
    tolerancia = abs(escala) * _TOLERANCIA_RELATIVA
    if valor > tolerancia:
        return 1
    if valor < -tolerancia:
        return -1
    return 0


def num(valor: float) -> str:
    """Número con dos decimales y punto decimal, para los motivos."""
    return f"{valor:.2f}"


def decidir(velas: ListaDoble[Vela], senal: Senal, confianza: float, motivo: str) -> Decision:
    """Decisión sobre la última vela (su tiempo y su cierre); la confianza se acota a [0, 1]."""
    ultima = velas.ultimo()
    return Decision(ultima.tiempo_apertura, senal, ultima.cierre, max(0.0, min(1.0, confianza)), motivo)


def faltan_velas(velas: ListaDoble[Vela] | None, necesarias: int) -> Decision:
    """MANTENER con confianza 0 porque todavía no hay velas suficientes."""
    hay = 0 if velas is None else velas.tamanio()
    tiempo = velas.ultimo().tiempo_apertura if velas is not None and hay else 0
    precio = velas.ultimo().cierre if velas is not None and hay else 0.0
    return Decision(tiempo, Senal.MANTENER, precio, 0.0,
                    f"Faltan velas para decidir: se necesitan al menos {necesarias} y hay {hay}.")


def agregar_ultimo(valores: dict[str, float], clave: str, serie: Serie) -> None:
    """Agrega el último valor de la serie, si tiene alguno."""
    if not serie.esta_vacia():
        valores[clave] = serie.ultimo().valor
