"""Endpoints de mercado: /health, /api/precio, /api/precio/recientes, /api/velas, /api/indicadores
y /api/si-hubiera.

Los endpoints solo traducen: leen y validan parámetros, llaman al dominio y
arman el JSON del contrato. Son funciones normales (no async): FastAPI las
corre en su grupo de hilos, así una consulta lenta a Binance no bloquea al resto.
"""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from bitcoinai.api.errores import ApiError
from bitcoinai.api.serializacion import caida_a_json, series_a_json, vela_a_json, velas_a_json
from bitcoinai.indicadores import crear_indicador, maxima_caida_de_velas
from bitcoinai.mercado import FuenteDeMercado, PreciosRecientes
from bitcoinai.modelo import Intervalo
from bitcoinai.simulacion.si_hubiera import FechaSinDatosError, IndiceVelas

CANTIDAD_MAXIMA = 1000
INTERVALO_POR_DEFECTO = "1d"
CANTIDAD_POR_DEFECTO = 200
MONTO_MAXIMO_SI_HUBIERA = 1_000_000


def crear_rutas_mercado(fuente: FuenteDeMercado, simbolo: str,
                        recientes: PreciosRecientes | None = None) -> APIRouter:
    """Crea el router con los endpoints de mercado."""
    rutas = APIRouter()
    precios_recientes = recientes or PreciosRecientes()

    @rutas.get("/health")
    def salud() -> dict[str, Any]:
        """Indica que el servicio está vivo. Nunca consulta Binance."""
        return {"estado": "ok"}

    @rutas.get("/api/precio")
    def precio() -> dict[str, Any]:
        """Último precio negociado del símbolo configurado."""
        valor = fuente.obtener_precio_actual(simbolo)
        momento = int(time.time() * 1000)
        precios_recientes.registrar(momento, valor)
        return {"simbolo": simbolo, "precio": valor, "momento": momento}

    @rutas.get("/api/precio/recientes")
    def recientes_() -> dict[str, Any]:
        """Los últimos precios que pasaron por el servidor (cola circular de 120), del más viejo al más nuevo.

        No consulta Binance: solo lee la memoria. Está vacía hasta que alguien pide
        el precio o se conecta al tiempo real.
        """
        precios = precios_recientes.instantanea()
        return {
            "simbolo": simbolo,
            "capacidad": precios_recientes.capacidad(),
            "cantidad": precios.tamanio(),
            "precios": [{"momento": m, "precio": p} for m, p in precios],
        }

    @rutas.get("/api/velas")
    def velas(intervalo: str = "", cantidad: str = "") -> dict[str, Any]:
        """Velas del símbolo configurado, de la más antigua a la más reciente."""
        intervalo_elegido = leer_intervalo(intervalo or INTERVALO_POR_DEFECTO)
        cantidad_elegida = leer_cantidad(cantidad or str(CANTIDAD_POR_DEFECTO))
        resultado = fuente.obtener_velas(simbolo, intervalo_elegido, cantidad_elegida)
        return {
            "simbolo": simbolo,
            "intervalo": intervalo_elegido.codigo,
            "cantidad": resultado.tamanio(),
            "velas": velas_a_json(resultado),
        }

    @rutas.get("/api/indicadores")
    def indicadores(peticion: Request, indicador: str = "", periodo: str = "", intervalo: str = "",
                    cantidad: str = "") -> dict[str, Any]:
        """Calcula un indicador técnico y devuelve sus series junto con las velas usadas.

        Además de ``periodo``, acepta ``rapido``, ``lento`` y ``senal`` (macd) y
        ``desviaciones`` (bollinger). Valida todo antes de consultar Binance.
        """
        try:
            elegido = crear_indicador(indicador, dict(peticion.query_params))
        except ValueError as error:
            raise ApiError(400, str(error)) from None
        intervalo_elegido = leer_intervalo(intervalo or INTERVALO_POR_DEFECTO)
        cantidad_elegida = leer_cantidad(cantidad or str(CANTIDAD_POR_DEFECTO))
        velas_usadas = fuente.obtener_velas(simbolo, intervalo_elegido, cantidad_elegida)
        return {
            "simbolo": simbolo,
            "intervalo": intervalo_elegido.codigo,
            "indicador": elegido.nombre(),
            "parametros": elegido.parametros(),
            "series": series_a_json(elegido.calcular_series(velas_usadas)),
            "maximaCaida": caida_a_json(maxima_caida_de_velas(velas_usadas)),
            "cantidad": velas_usadas.tamanio(),
            "velas": velas_a_json(velas_usadas),
        }

    @rutas.get("/api/si-hubiera")
    def si_hubiera(fecha: str = "", monto: str = "") -> dict[str, Any]:
        """Cuánto valdría hoy una compra hecha al abrir el día ``fecha`` (AAAA-MM-DD, UTC).

        Indexa las últimas 1000 velas diarias en un árbol AVL: la de esa fecha sale
        con ``techo`` en O(log n) y el mejor y el peor momento con ``rango``.
        """
        fecha_ms = leer_fecha(fecha)
        monto_usdt = leer_monto(monto)
        indice = IndiceVelas(fuente.obtener_velas(simbolo, Intervalo.D1, CANTIDAD_MAXIMA))
        try:
            r = indice.si_hubiera(fecha_ms, monto_usdt, fuente.obtener_precio_actual(simbolo))
        except FechaSinDatosError as error:
            desde = "—" if indice.arbol.esta_vacio() else fecha_texto(indice.desde())
            raise ApiError(400, f"{error}. Hay datos desde el {desde}.") from None
        return {
            "fecha": fecha.strip(),
            "monto": r.monto,
            "vela": vela_a_json(r.vela),
            "btc": r.btc,
            "precioActual": r.precio_actual,
            "valorHoy": r.valor_hoy,
            "ganancia": r.ganancia,
            "rentabilidad": r.rentabilidad,
            "mejor": {"tiempo": r.mejor.tiempo, "precio": r.mejor.precio},
            "peor": {"tiempo": r.peor.tiempo, "precio": r.peor.precio},
            "velasRecorridas": r.velas_recorridas,
            "alturaArbol": indice.arbol.altura(),
            "velasIndexadas": indice.arbol.tamanio(),
        }

    return rutas


def fecha_texto(milisegundos: int) -> str:
    """AAAA-MM-DD (UTC) de un momento en milisegundos."""
    return datetime.fromtimestamp(milisegundos / 1000, UTC).date().isoformat()


def leer_fecha(texto: str) -> int:
    """Fecha AAAA-MM-DD del pasado, en milisegundos (medianoche UTC), o 400."""
    try:
        dia = datetime.strptime(texto.strip(), "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        raise ApiError(400, f"Parámetro 'fecha' inválido: '{texto}'. Usa el formato AAAA-MM-DD") from None
    if dia > datetime.now(UTC):
        raise ApiError(400, "La fecha no puede estar en el futuro")
    return int(dia.timestamp() * 1000)


def leer_monto(texto: str) -> float:
    """Monto en USDT mayor que 0 y hasta un millón, o 400."""
    try:
        monto = float(texto.strip())
    except ValueError:
        monto = 0.0
    if not 0 < monto <= MONTO_MAXIMO_SI_HUBIERA:
        raise ApiError(400, f"Parámetro 'monto' inválido: '{texto}'. Debe ser mayor que 0 y como máximo "
                            f"{MONTO_MAXIMO_SI_HUBIERA}")
    return monto


def leer_intervalo(texto: str) -> Intervalo:
    """Intervalo de un parámetro, o 400 con los valores permitidos."""
    try:
        return Intervalo.desde_codigo(texto)
    except ValueError:
        raise ApiError(400, f"Parámetro 'intervalo' inválido: '{texto}'. "
                            "Valores permitidos: 1m, 5m, 15m, 1h, 4h, 1d") from None


def leer_cantidad(texto: str) -> int:
    """Cantidad de velas entre 1 y 1000, o 400 con el motivo."""
    try:
        cantidad = int(texto.strip())
    except ValueError:
        cantidad = 0
    if not 1 <= cantidad <= CANTIDAD_MAXIMA:
        raise ApiError(400, f"Parámetro 'cantidad' inválido: '{texto}'. "
                            f"Debe ser un número entero entre 1 y {CANTIDAD_MAXIMA}")
    return cantidad
