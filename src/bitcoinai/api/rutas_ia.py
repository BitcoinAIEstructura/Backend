"""GET /api/ia/predicciones?intervalo=1h: lo que creen los modelos de la vela siguiente.

Es pública (solo usa datos de mercado). La primera petición de cada intervalo
entrena (unos segundos); las siguientes, durante 10 minutos, salen de la caché.
"""

from typing import Any

from fastapi import APIRouter

from bitcoinai.api.errores import ApiError
from bitcoinai.ia.arbol import NodoDecision
from bitcoinai.ia.caracteristicas import NOMBRES
from bitcoinai.ia.evaluacion import Metricas
from bitcoinai.ia.servicio import DatosInsuficientesError, ResultadoModelo, ServicioIA
from bitcoinai.mercado import FuenteDeMercado
from bitcoinai.modelo import Intervalo

INTERVALOS_IA = ("15m", "1h", "4h", "1d")


def _metricas(m: Metricas) -> dict[str, Any]:
    return {"muestras": m.muestras, "exactitud": m.exactitud, "base": m.base, "ventaja": m.ventaja,
            "precisionSube": m.precision_sube, "vecesDijoSube": m.veces_dijo_sube}


def _modelo(r: ResultadoModelo) -> dict[str, Any]:
    return {
        "nombre": r.nombre,
        "probabilidad": r.probabilidad,
        "direccion": r.direccion,
        "confianza": r.confianza,
        "peso": r.peso,
        "explicacion": {
            "resumen": r.explicacion.resumen,
            "factores": [{"nombre": n, "peso": p} for n, p in r.explicacion.factores],
            "pasos": list(r.explicacion.pasos),
        },
        "metricas": _metricas(r.metricas),
    }


def _nodo(n: NodoDecision | None, x: tuple[float, ...], en_camino: bool) -> dict[str, Any] | None:
    """El árbol, marcando las ramas por las que pasó la vela de ahora."""
    if n is None:
        return None
    if n.caracteristica is None:
        return {"hoja": True, "muestras": n.muestras, "probabilidad": n.probabilidad, "enCamino": en_camino}
    va_si = x[n.caracteristica] <= n.umbral
    return {
        "hoja": False,
        "caracteristica": NOMBRES[n.caracteristica],
        "umbral": n.umbral,
        "muestras": n.muestras,
        "probabilidad": n.probabilidad,
        "enCamino": en_camino,
        "si": _nodo(n.si, x, en_camino and va_si),
        "no": _nodo(n.no, x, en_camino and not va_si),
    }


def crear_rutas_ia(fuente: FuenteDeMercado, simbolo: str, servicio: ServicioIA | None = None) -> APIRouter:
    rutas = APIRouter()
    ia = servicio or ServicioIA(fuente, simbolo)

    @rutas.get("/api/ia/predicciones")
    def predicciones(intervalo: str = "") -> dict[str, Any]:
        codigo = intervalo.strip() or "1h"
        if codigo not in INTERVALOS_IA:
            raise ApiError(400, f"Parámetro 'intervalo' inválido: '{intervalo}'. "
                                f"Valores permitidos: {', '.join(INTERVALOS_IA)}")
        try:
            p = ia.predecir(Intervalo.desde_codigo(codigo))
        except DatosInsuficientesError as error:
            raise ApiError(503, str(error)) from None
        return {
            "simbolo": simbolo,
            "intervalo": p.intervalo,
            "tiempoVela": p.tiempo_vela,
            "entrenadoEn": p.entrenado_en,
            "muestrasEntrenamiento": p.muestras_entrenamiento,
            "muestrasPrueba": p.muestras_prueba,
            "comite": _modelo(p.comite),
            "modelos": [_modelo(m) for m in p.modelos],
            "caracteristicas": [{"nombre": n, "valor": v} for n, v in zip(NOMBRES, p.caracteristicas, strict=True)],
            "arbol": _nodo(p.arbol, p.caracteristicas, True),
            "prueba": [{"tiempo": q.tiempo, "probabilidad": q.probabilidad, "subio": q.subio} for q in p.prueba],
            "aviso": p.aviso,
        }

    return rutas
