"""Clientes de las fuentes externas. Todas son públicas: no hay cuentas ni claves de API.

- **Índice de miedo y codicia** (alternative.me): el ánimo del mercado de 0 a 100, un valor
  por día desde 2018.
- **Futuros de Binance** (fapi.binance.com, datos públicos): la tasa de financiación cada
  8 horas y qué parte de las cuentas apuesta a que sube.
- **Deribit** (www.deribit.com, datos públicos): el DVOL, la volatilidad que el mercado de
  opciones espera para los próximos 30 días (anualizada, en %).

Solo se leen datos; nunca se opera ni se conecta una cuenta.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from bitcoinai.externos.serie import SerieTemporal

URL_MIEDO_CODICIA = "https://api.alternative.me/fng/"
URL_FUTUROS_BINANCE = "https://fapi.binance.com"
URL_DERIBIT = "https://www.deribit.com/api/v2/public"

HORA_MS = 3_600_000
DIA_MS = 24 * HORA_MS
MAXIMO_PAGINAS = 8
"""Tope de peticiones seguidas a una misma fuente (cada una trae hasta 1000 datos)."""


class FuenteExternaError(Exception):
    """Una fuente externa no respondió o respondió algo que no se entiende."""


class ClienteExternos:
    """Lee las tres fuentes. En las pruebas se le pasa un ``httpx.Client`` con ``MockTransport``."""

    def __init__(self, cliente_http: httpx.Client | None = None, espera_s: float = 10.0) -> None:
        self._http = cliente_http or httpx.Client(
            timeout=httpx.Timeout(espera_s, connect=5.0), headers={"User-Agent": "Nexabit/1.0 (proyecto educativo)"})

    def _json(self, url: str, parametros: dict[str, str | int]) -> Any:
        try:
            respuesta = self._http.get(url, params=parametros)
        except httpx.HTTPError as error:
            raise FuenteExternaError(f"No respondió ({type(error).__name__})") from None
        if respuesta.status_code != 200:
            raise FuenteExternaError(f"Respondió {respuesta.status_code}")
        try:
            return respuesta.json()
        except json.JSONDecodeError:
            raise FuenteExternaError("Respondió algo que no es JSON") from None

    # ---------- miedo y codicia ----------

    def miedo_codicia(self) -> tuple[SerieTemporal, str]:
        """Toda la historia (un valor por día) y la clasificación del último valor, en inglés.

        Raises:
            FuenteExternaError
        """
        datos = self._json(URL_MIEDO_CODICIA, {"limit": 0, "format": "json"})
        serie = SerieTemporal("Miedo y codicia")
        clasificacion = ""
        try:
            for fila in datos["data"]:
                # El valor del día se publica al empezar el día (UTC): se conoce desde ese momento.
                serie.agregar(int(fila["timestamp"]) * 1000, float(fila["value"]))
            if datos["data"]:
                clasificacion = str(datos["data"][0]["value_classification"])
        except (KeyError, TypeError, ValueError):
            raise FuenteExternaError("El índice de miedo y codicia llegó con otra forma") from None
        if serie.tamanio() == 0:
            raise FuenteExternaError("El índice de miedo y codicia llegó vacío")
        return serie, clasificacion

    # ---------- futuros de Binance ----------

    def financiacion(self, desde_ms: int, hasta_ms: int) -> SerieTemporal:
        """Tasas de financiación de BTCUSDT perpetuo desde ``desde_ms`` (una cada 8 horas).

        Raises:
            FuenteExternaError
        """
        serie = SerieTemporal("Financiación de futuros")
        inicio = desde_ms
        for _ in range(MAXIMO_PAGINAS):
            lote = self._json(f"{URL_FUTUROS_BINANCE}/fapi/v1/fundingRate",
                              {"symbol": "BTCUSDT", "startTime": inicio, "endTime": hasta_ms, "limit": 1000})
            if not isinstance(lote, list):
                raise FuenteExternaError("La financiación llegó con otra forma")
            try:
                for fila in lote:
                    serie.agregar(int(fila["fundingTime"]), float(fila["fundingRate"]))
            except (KeyError, TypeError, ValueError):
                raise FuenteExternaError("La financiación llegó con otra forma") from None
            if len(lote) < 1000:
                break
            inicio = int(lote[-1]["fundingTime"]) + 1
        if serie.tamanio() == 0:
            raise FuenteExternaError("No llegaron tasas de financiación")
        return serie

    def largos_y_cortos(self) -> float:
        """Qué parte de las cuentas con futuros apuesta a que sube (0 a 1), en la última hora.

        Raises:
            FuenteExternaError
        """
        datos = self._json(f"{URL_FUTUROS_BINANCE}/futures/data/globalLongShortAccountRatio",
                           {"symbol": "BTCUSDT", "period": "1h", "limit": 1})
        try:
            return float(datos[-1]["longAccount"])
        except (KeyError, IndexError, TypeError, ValueError):
            raise FuenteExternaError("La proporción de largos y cortos llegó con otra forma") from None

    # ---------- Deribit ----------

    def dvol(self, desde_ms: int, hasta_ms: int, resolucion: str) -> SerieTemporal:
        """El DVOL (cierre de cada periodo) desde ``desde_ms``. ``resolucion``: "3600", "43200" o "1D".

        Deribit entrega hasta 1000 datos por petición, de los más nuevos hacia atrás, y dice
        dónde seguir (``continuation``).

        Raises:
            FuenteExternaError
        """
        periodo = {"3600": HORA_MS, "43200": 12 * HORA_MS, "1D": DIA_MS}[resolucion]
        serie = SerieTemporal("DVOL de Deribit")
        fin = hasta_ms
        for _ in range(MAXIMO_PAGINAS):
            datos = self._json(f"{URL_DERIBIT}/get_volatility_index_data",
                               {"currency": "BTC", "resolution": resolucion, "start_timestamp": desde_ms,
                                "end_timestamp": fin})
            try:
                resultado = datos["result"]
                for fila in resultado["data"]:
                    # [inicio, apertura, máximo, mínimo, cierre]: el cierre se conoce al terminar el periodo.
                    serie.agregar(int(fila[0]) + periodo, float(fila[4]))
                seguir = resultado.get("continuation")
            except (KeyError, IndexError, TypeError, ValueError):
                raise FuenteExternaError("El DVOL llegó con otra forma") from None
            if not seguir or int(seguir) <= desde_ms:
                break
            fin = int(seguir)
        if serie.tamanio() == 0:
            raise FuenteExternaError("No llegó el DVOL")
        return serie
