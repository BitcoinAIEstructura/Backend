"""Estadísticas de la simulación de un usuario, para las gráficas del panel.

Se calculan con el registro de órdenes ejecutadas, repitiéndolas sobre una cartera
nueva (la misma contabilidad que la real): así cada venta sabe cuánto ganó o perdió.
Complejidad total: O(n + d) con n órdenes y d días.
"""

from dataclasses import dataclass

from bitcoinai.estructuras import Lista
from bitcoinai.simulacion.cartera import Cartera
from bitcoinai.simulacion.modelo import EstadoOrden, OperacionRechazadaError, Orden, TipoOrden

DIA_MS = 86_400_000
DESFASE_BOGOTA_MS = -5 * 3_600_000
"""Colombia está en UTC−5 todo el año: los días se cortan a la medianoche de Bogotá."""

ORIGENES = ("manual", "bot", "ia")


def origen_de(orden: Orden) -> str:
    """Quién creó la orden: "ia" (piloto IA), "bot" (estrategia o stop/take) o "manual"."""
    motivo = orden.motivo.lower()
    if motivo.startswith("piloto ia"):
        return "ia"
    if motivo.startswith(("señal del bot", "stop-loss", "take-profit")):
        return "bot"
    return "manual"


def dia_de(momento_ms: int) -> int:
    """Inicio (ms UTC) del día de Bogotá que contiene ``momento_ms``."""
    return (momento_ms + DESFASE_BOGOTA_MS) // DIA_MS * DIA_MS - DESFASE_BOGOTA_MS


@dataclass(frozen=True, slots=True)
class OperacionCerrada:
    """Una venta ejecutada: cuánto ganó (o perdió) frente a lo que había costado ese BTC."""

    id_orden: int
    tiempo: int
    ganancia: float
    rentabilidad: float
    origen: str


@dataclass(frozen=True, slots=True)
class ActividadDia:
    dia: int
    compras: int
    ventas: int
    volumen: float


@dataclass(frozen=True, slots=True)
class Estadisticas:
    operaciones: Lista[OperacionCerrada]
    actividad: Lista[ActividadDia]
    ganadoras: int
    perdedoras: int
    ganancia_promedio: float
    mejor: float | None
    peor: float | None
    volumen_total: float
    por_origen: dict[str, int]
    ganancia_por_origen: dict[str, float]

    @property
    def tasa_acierto(self) -> float | None:
        cerradas = self.ganadoras + self.perdedoras
        return self.ganadoras / cerradas if cerradas else None


def calcular(ordenes: Lista[Orden], saldo_inicial: float, comision: float, ahora_ms: int,
             dias: int = 30) -> Estadisticas:
    """Estadísticas de las órdenes (en el orden en que terminaron) de los últimos ``dias`` días.

    La comisión de cada orden ya viene en ella; ``comision`` solo sirve para repetir la
    cuenta igual que la cartera real.
    """
    cartera = Cartera(saldo_inicial)
    operaciones: Lista[OperacionCerrada] = Lista()
    por_dia: dict[int, tuple[int, int, float]] = {}
    por_origen = dict.fromkeys(ORIGENES, 0)
    ganancia_por_origen = dict.fromkeys(ORIGENES, 0.0)
    volumen_total = 0.0
    for orden in ordenes:
        if orden.estado is not EstadoOrden.EJECUTADA or orden.precio_ejecucion is None or orden.ejecutada_en is None:
            continue
        precio = orden.precio_ejecucion
        origen = origen_de(orden)
        por_origen[origen] += 1
        volumen = (orden.cantidad_btc or 0.0) * precio
        volumen_total += volumen
        compras, ventas, vol_dia = por_dia.get(dia_de(orden.ejecutada_en), (0, 0, 0.0))
        try:
            if orden.tipo is TipoOrden.COMPRA:
                cartera.comprar(orden.monto or 0.0, precio, comision)
                compras += 1
            else:
                costo_antes = cartera.costo_posicion
                antes = cartera.ganancia_realizada
                cantidad = min(orden.cantidad_btc or cartera.btc, cartera.btc)
                if cantidad <= 0:
                    continue
                vendido = cantidad / cartera.btc
                cartera.vender(cantidad * precio, precio, comision)
                ganancia = cartera.ganancia_realizada - antes
                costo = costo_antes * vendido
                operaciones.agregar(OperacionCerrada(orden.id, orden.ejecutada_en, ganancia,
                                                     ganancia / costo if costo > 0 else 0.0, origen))
                ganancia_por_origen[origen] += ganancia
                ventas += 1
        except OperacionRechazadaError:
            continue  # no debería pasar con órdenes ya ejecutadas; si pasa, se ignora esa orden
        por_dia[dia_de(orden.ejecutada_en)] = (compras, ventas, vol_dia + volumen)

    actividad: Lista[ActividadDia] = Lista()
    hoy = dia_de(ahora_ms)
    for atras in range(dias - 1, -1, -1):
        dia = hoy - atras * DIA_MS
        compras, ventas, vol = por_dia.get(dia, (0, 0, 0.0))
        actividad.agregar(ActividadDia(dia, compras, ventas, vol))

    ganadoras = perdedoras = 0
    suma = 0.0
    mejor: float | None = None
    peor: float | None = None
    for op in operaciones:
        suma += op.ganancia
        if op.ganancia > 0:
            ganadoras += 1
        else:
            perdedoras += 1
        mejor = op.ganancia if mejor is None else max(mejor, op.ganancia)
        peor = op.ganancia if peor is None else min(peor, op.ganancia)
    n = operaciones.tamanio()
    return Estadisticas(operaciones, actividad, ganadoras, perdedoras, suma / n if n else 0.0, mejor, peor,
                        volumen_total, por_origen, ganancia_por_origen)
