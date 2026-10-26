"""La IA por HTTP. Es pública (solo usa datos de mercado).

- ``GET /api/ia/predicciones?intervalo=1h``: lo que creen los modelos de la vela siguiente. La
  primera petición de cada intervalo entrena (unos segundos); las siguientes, durante 10 minutos,
  salen de la caché. Trae también los textos que muestra la página (qué hace cada modelo, el
  veredicto frente a la base y si las fuentes externas ayudaron): el frontend solo los dibuja.
- ``GET /api/ia/fuentes?intervalo=1h``: lo que dicen ahora las fuentes externas, explicado.
"""

from typing import Any

from fastapi import APIRouter

from bitcoinai.api.errores import ApiError
from bitcoinai.externos import DatosExternos
from bitcoinai.ia import textos
from bitcoinai.ia.arbol import NodoDecision
from bitcoinai.ia.caracteristicas import FUENTES_EXTERNAS
from bitcoinai.ia.evaluacion import Metricas
from bitcoinai.ia.servicio import DatosInsuficientesError, ResultadoModelo, ServicioIA
from bitcoinai.mercado import FuenteDeMercado, MercadoError
from bitcoinai.modelo import Intervalo

INTERVALOS_IA = tuple(codigo for codigo, _ in textos.INTERVALOS)
NOMBRE_FUENTE = {f.id: f.nombre for f in FUENTES_EXTERNAS}


def _metricas(m: Metricas) -> dict[str, Any]:
    return {"muestras": m.muestras, "exactitud": m.exactitud, "base": m.base, "ventaja": m.ventaja,
            "precisionSube": m.precision_sube, "vecesDijoSube": m.veces_dijo_sube}


def _modelo(r: ResultadoModelo) -> dict[str, Any]:
    descripcion = textos.descripcion(r.nombre)
    veredicto = textos.veredicto(r.metricas)
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
        "descripcion": {"idea": descripcion.idea, "tituloFactores": descripcion.titulo_factores,
                        "factoresConSigno": descripcion.factores_con_signo},
        "veredicto": {"gana": veredicto.gana, "titulo": veredicto.titulo, "texto": veredicto.texto},
    }


def _nodo(n: NodoDecision | None, x: tuple[float, ...], nombres: tuple[str, ...],
          en_camino: bool) -> dict[str, Any] | None:
    """El árbol, marcando las ramas por las que pasó la vela de ahora."""
    if n is None:
        return None
    if n.caracteristica is None:
        return {"hoja": True, "muestras": n.muestras, "probabilidad": n.probabilidad, "enCamino": en_camino}
    va_si = x[n.caracteristica] <= n.umbral
    return {
        "hoja": False,
        "caracteristica": nombres[n.caracteristica],
        "umbral": n.umbral,
        "muestras": n.muestras,
        "probabilidad": n.probabilidad,
        "enCamino": en_camino,
        "si": _nodo(n.si, x, nombres, en_camino and va_si),
        "no": _nodo(n.no, x, nombres, en_camino and not va_si),
    }


def _leer_intervalo(intervalo: str) -> Intervalo:
    codigo = intervalo.strip() or "1h"
    if codigo not in INTERVALOS_IA:
        raise ApiError(400, f"Parámetro 'intervalo' inválido: '{intervalo}'. "
                            f"Valores permitidos: {', '.join(INTERVALOS_IA)}")
    return Intervalo.desde_codigo(codigo)


def crear_rutas_ia(fuente: FuenteDeMercado, simbolo: str, servicio: ServicioIA | None = None,
                   externos: DatosExternos | None = None) -> APIRouter:
    rutas = APIRouter()
    ia = servicio or ServicioIA(fuente, simbolo, externos=externos)

    @rutas.get("/api/ia/predicciones")
    def predicciones(intervalo: str = "") -> dict[str, Any]:
        elegido = _leer_intervalo(intervalo)
        try:
            p = ia.predecir(elegido)
        except DatosInsuficientesError as error:
            raise ApiError(503, str(error)) from None
        comparacion = None
        if p.comparacion is not None:
            comparacion = {
                "sinExternos": _metricas(p.comparacion.sin_externos),
                "conExternos": _metricas(p.comparacion.con_externos),
                "conclusion": textos.conclusion_externos(p.comparacion.sin_externos, p.comparacion.con_externos),
            }
        return {
            "simbolo": simbolo,
            "intervalo": p.intervalo,
            "nombreIntervalo": textos.nombre_intervalo(p.intervalo),
            "intervalos": [{"codigo": c, "nombre": n} for c, n in textos.INTERVALOS],
            "encabezado": textos.ENCABEZADO,
            "tiempoVela": p.tiempo_vela,
            "entrenadoEn": p.entrenado_en,
            "muestrasEntrenamiento": p.muestras_entrenamiento,
            "muestrasPrueba": p.muestras_prueba,
            "comite": _modelo(p.comite),
            "modelos": [_modelo(m) for m in p.modelos],
            "caracteristicas": [{"nombre": n, "valor": v} for n, v in zip(p.nombres, p.caracteristicas, strict=True)],
            "arbol": _nodo(p.arbol, p.caracteristicas, p.nombres, True),
            "prueba": [{"tiempo": q.tiempo, "probabilidad": q.probabilidad, "subio": q.subio} for q in p.prueba],
            "fuentesExternas": {
                "usadas": [{"id": f, "nombre": NOMBRE_FUENTE.get(f, f)} for f in p.fuentes_usadas],
                "omitidas": [{"id": f, "nombre": NOMBRE_FUENTE.get(f, f), "motivo": motivo}
                             for f, motivo in p.fuentes_omitidas.items()],
                "comparacion": comparacion,
            },
            "aviso": p.aviso,
        }

    @rutas.get("/api/ia/fuentes")
    def fuentes(intervalo: str = "") -> dict[str, Any]:
        elegido = _leer_intervalo(intervalo)
        if externos is None:
            return {"lecturas": [], "errores": [], "actualizadoEn": None}
        try:
            precio: float | None = fuente.obtener_precio_actual(simbolo)
        except MercadoError:
            precio = None
        panorama = externos.panorama(elegido, precio)
        return {
            "lecturas": [{"id": lec.id, "nombre": lec.nombre, "fuente": lec.fuente, "valor": lec.valor,
                          "valorTexto": lec.valor_texto, "explicacion": lec.explicacion}
                         for lec in panorama.lecturas],
            "errores": [{"id": f, "motivo": motivo} for f, motivo in panorama.errores.items()],
            "actualizadoEn": panorama.actualizado_en,
        }

    return rutas
