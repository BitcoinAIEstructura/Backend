"""Conversión del dominio al JSON del contrato (borde de la API).

El contrato usa nombres en camelCase (``tiempoApertura``), como la versión
Java. Aquí, y solo aquí, las estructuras propias se convierten a ``list``
para que FastAPI escriba el JSON.
"""

from typing import Any

from bitcoinai.estrategia import (
    Decision,
    OperacionCerrada,
    Pronostico,
    ResultadoBacktest,
    ResultadoValidacion,
    ResumenCandidato,
)
from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores import PuntoIndicador, ResultadoCaida, Serie
from bitcoinai.modelo import Vela


def vela_a_json(vela: Vela) -> dict[str, Any]:
    """Una vela con los nombres del contrato. Complejidad: O(1)."""
    return {
        "tiempoApertura": vela.tiempo_apertura,
        "apertura": vela.apertura,
        "maximo": vela.maximo,
        "minimo": vela.minimo,
        "cierre": vela.cierre,
        "volumen": vela.volumen,
        "tiempoCierre": vela.tiempo_cierre,
    }


def velas_a_json(velas: ListaDoble[Vela]) -> list[dict[str, Any]]:
    """Las velas en orden, como arreglo JSON. Complejidad: O(n)."""
    return [vela_a_json(vela) for vela in velas]


def punto_a_json(punto: PuntoIndicador) -> dict[str, Any]:
    """Un punto de indicador: ``{"tiempo", "valor"}``. Complejidad: O(1)."""
    return {"tiempo": punto.tiempo, "valor": punto.valor}


def serie_a_json(serie: Serie) -> list[dict[str, Any]]:
    """Una serie de puntos como arreglo JSON. Complejidad: O(n)."""
    return [punto_a_json(punto) for punto in serie]


def series_a_json(series: dict[str, Serie]) -> dict[str, Any]:
    """Series con nombre, por ejemplo ``{"macd": [...], "senal": [...]}``. Complejidad: O(n)."""
    return {nombre: serie_a_json(serie) for nombre, serie in series.items()}


def decision_a_json(decision: Decision) -> dict[str, Any]:
    """Una decisión: ``{tiempo, senal, precio, confianza, motivo}``. Complejidad: O(1)."""
    return {
        "tiempo": decision.tiempo,
        "senal": decision.senal.name,
        "precio": decision.precio,
        "confianza": decision.confianza,
        "motivo": decision.motivo,
    }


def pronostico_a_json(pronostico: Pronostico) -> dict[str, Any]:
    """Un pronóstico, con el aviso fijo. Complejidad: O(k) con k frases."""
    return {
        "direccion": pronostico.direccion.name,
        "confianza": pronostico.confianza,
        "justificacion": list(pronostico.justificacion),
        "indicadores": dict(pronostico.indicadores),
        "aviso": pronostico.aviso,
    }


def operacion_a_json(operacion: OperacionCerrada) -> dict[str, Any]:
    """Una operación cerrada del backtest. Complejidad: O(1)."""
    return {
        "tiempoEntrada": operacion.tiempo_entrada,
        "precioEntrada": operacion.precio_entrada,
        "tiempoSalida": operacion.tiempo_salida,
        "precioSalida": operacion.precio_salida,
        "cantidadBtc": operacion.cantidad_btc,
        "comisiones": operacion.comisiones,
        "ganancia": operacion.ganancia,
        "rentabilidad": operacion.rentabilidad,
        "motivoSalida": operacion.motivo_salida,
    }


def backtest_a_json(r: ResultadoBacktest) -> dict[str, Any]:
    """Resultado completo de un backtest. Complejidad: O(n)."""
    return {
        "estrategia": r.estrategia,
        "parametros": r.parametros,
        "capitalInicial": r.capital_inicial,
        "comision": r.comision,
        "capitalFinal": r.capital_final,
        "rentabilidadTotal": r.rentabilidad_total,
        "rentabilidadComprarYMantener": r.rentabilidad_comprar_y_mantener,
        "numeroOperaciones": r.numero_operaciones,
        "tasaGanadoras": r.tasa_ganadoras,
        "caidaMaxima": r.caida_maxima,
        "factorBeneficio": r.factor_beneficio,
        "comisionesPagadas": r.comisiones_pagadas,
        "velasAnalizadas": r.velas_analizadas,
        "numeroDecisiones": r.numero_decisiones,
        "tiempoInicio": r.tiempo_inicio,
        "tiempoFin": r.tiempo_fin,
        "operaciones": [operacion_a_json(o) for o in r.operaciones],
        "decisionesRecientes": [decision_a_json(d) for d in r.decisiones_recientes],
        "curvaCapital": serie_a_json(r.curva_capital),
    }


def candidato_a_json(c: ResumenCandidato) -> dict[str, Any]:
    """Resumen de un candidato de la validación. Complejidad: O(1)."""
    return {"parametros": c.parametros, "rentabilidad": c.rentabilidad, "numeroOperaciones": c.numero_operaciones}


def validacion_a_json(v: ResultadoValidacion) -> dict[str, Any]:
    """Resultado de la validación entrenamiento/prueba. Complejidad: O(n)."""
    return {
        "estrategia": v.estrategia,
        "fraccionEntrenamiento": v.fraccion_entrenamiento,
        "velasEntrenamiento": v.velas_entrenamiento,
        "velasPrueba": v.velas_prueba,
        "parametrosElegidos": v.parametros_elegidos,
        "candidatos": [candidato_a_json(c) for c in v.candidatos],
        "entrenamiento": backtest_a_json(v.entrenamiento),
        "prueba": backtest_a_json(v.prueba),
    }


def caida_a_json(caida: ResultadoCaida) -> dict[str, Any]:
    """Máxima caída con los nombres del contrato. Complejidad: O(1)."""
    return {
        "caidaMaxima": caida.caida_maxima,
        "tiempoPico": caida.tiempo_pico,
        "valorPico": caida.valor_pico,
        "tiempoValle": caida.tiempo_valle,
        "valorValle": caida.valor_valle,
    }
