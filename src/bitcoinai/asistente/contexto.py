"""Los datos de práctica que se le cuentan a Claude en cada mensaje del chat.

Solo la simulación: cartera, bot, órdenes recientes y el consejo de la IA. Ningún dato
personal (ni el nombre). Es texto plano corto para que Claude lo lea fácil y cueste poco.
"""

from bitcoinai.asistente.asistente import DatosUsuario, decimal, usdt
from bitcoinai.estructuras import Lista
from bitcoinai.simulacion import ConsejoPiloto, EstadoOrden, Orden

ORDENES_RECIENTES = 5


def _porcentaje(fraccion: float, decimales: int = 1) -> str:
    return f"{decimal(fraccion * 100, decimales)} %"


def armar_contexto(datos: DatosUsuario, ordenes: Lista[Orden], consejo: ConsejoPiloto | None) -> str:
    """Las líneas de ``<datos_de_practica>``. Complejidad: O(n) en las órdenes."""
    lineas = Lista[str]()
    c = datos.cartera
    if c is None:
        lineas.agregar("Cartera: no se pudo valorar ahora (el precio del mercado no respondió).")
    else:
        lineas.agregar(f"Precio de BTC ahora: {usdt(c.precio_actual)} USDT.")
        lineas.agregar(f"Cartera: vale {usdt(c.valor_total)} USDT (empezó con {usdt(c.saldo_inicial)}); "
                       f"ganancia total {usdt(c.ganancia_total)} USDT ({_porcentaje(c.rentabilidad, 2)}).")
        lineas.agregar(f"Tiene {usdt(c.saldo_usdt)} USDT disponibles y {decimal(c.btc, 8)} BTC "
                       f"(valen {usdt(c.valor_btc)} USDT; costo promedio {usdt(c.costo_promedio)}).")
        lineas.agregar(f"Ganancia realizada {usdt(c.ganancia_realizada)}, no realizada "
                       f"{usdt(c.ganancia_no_realizada)}, comisiones pagadas {usdt(c.comisiones_pagadas)} USDT.")
    b = datos.bot
    modo = "piloto IA" if b.configuracion.modo == "ia" else "reglas (cruce de medias, RSI y MACD)"
    estado = "encendido" if b.activo else "apagado"
    lineas.agregar(f"Bot: {estado}, modo {modo}, velas de {b.configuracion.intervalo}, riesgo "
                   f"{_porcentaje(b.configuracion.riesgo, 0)}, stop-loss {_porcentaje(b.configuracion.stop_loss)}, "
                   f"take-profit {_porcentaje(b.configuracion.take_profit)}; revisó el mercado {b.ciclos} veces.")
    if b.ultima_decision is not None:
        d = b.ultima_decision
        lineas.agregar(f"Última decisión del bot: {d.senal.name} (confianza {decimal(d.confianza)}): {d.motivo}")
    if b.ultimo_error:
        lineas.agregar(f"Último error del bot: {b.ultimo_error}")
    lineas.agregar(f"Órdenes pendientes en la cola: {datos.pendientes}.")
    ejecutadas = Lista[Orden]()
    for orden in ordenes:
        if orden.estado is EstadoOrden.EJECUTADA:
            ejecutadas.agregar(orden)
    if ejecutadas.esta_vacia():
        lineas.agregar("Todavía no tiene órdenes ejecutadas.")
    else:
        lineas.agregar(f"Órdenes ejecutadas en total: {ejecutadas.tamanio()}. Las más recientes:")
        desde = max(0, ejecutadas.tamanio() - ORDENES_RECIENTES)
        for indice, o in enumerate(ejecutadas):
            if indice >= desde:
                lineas.agregar(f"- #{o.id} {o.tipo.name} de {decimal(o.cantidad_btc or 0, 8)} BTC a "
                               f"{usdt(o.precio_ejecucion or 0)} ({o.motivo[:80]})")
    if consejo is not None:
        lineas.agregar(f"Consejo actual de la IA (velas de {consejo.intervalo}): {consejo.senal}; probabilidad "
                       f"de que suba {_porcentaje(consejo.probabilidad, 0)}; en datos no vistos acertó "
                       f"{_porcentaje(consejo.exactitud, 0)} (base {_porcentaje(consejo.base, 0)}).")
    return "\n".join(lineas)
