"""Cliente de la API pública de Binance (no necesita clave)."""

from __future__ import annotations

import json
import os
import re
import time
from types import TracebackType
from typing import Any, Final

import httpx

from bitcoinai.estructuras import ListaDoble
from bitcoinai.mercado.errores import MercadoError
from bitcoinai.mercado.validacion import validar_velas
from bitcoinai.modelo import Intervalo, Vela

URL_BASE_POR_DEFECTO: Final = "https://api.binance.com"
"""URL base por defecto de la API de Binance."""

LIMITE_POR_PETICION: Final = 1000
"""Máximo de velas que Binance entrega en una sola petición."""

_SIMBOLO_VALIDO: Final = re.compile(r"[A-Z0-9]{2,20}")


class ClienteBinance:
    """Fuente de mercado que consulta la API pública de Binance.

    - ``GET /api/v3/klines``: velas; cada una llega como un arreglo
      ``[tiempo_apertura, "apertura", "maximo", "minimo", "cierre", "volumen", tiempo_cierre, ...]``.
    - ``GET /api/v3/ticker/price``: último precio, ``{"symbol": "BTCUSDT", "price": "67000.00"}``.

    La URL base sale de la variable de entorno ``BINANCE_BASE_URL`` (por defecto
    https://api.binance.com), porque en algunos países hay que cambiarla.
    Reintenta ante fallos de red, tiempo agotado o errores 5xx; los 4xx no se
    reintentan, porque repetir la misma petición no los arregla.
    """

    def __init__(
        self,
        url_base: str | None = None,
        *,
        cliente_http: httpx.Client | None = None,
        tiempo_conexion: float = 5.0,
        tiempo_respuesta: float = 10.0,
        reintentos: int = 1,
        pausa_reintento: float = 0.5,
    ) -> None:
        """Crea el cliente.

        Args:
            url_base: URL base; si es None se usa ``BINANCE_BASE_URL`` o la de por defecto.
            cliente_http: cliente httpx propio (en pruebas, uno con ``MockTransport``).
            tiempo_conexion: segundos máximos para conectar.
            tiempo_respuesta: segundos máximos de espera de cada respuesta.
            reintentos: reintentos ante fallos de red o errores 5xx.
            pausa_reintento: segundos de espera antes de cada reintento.
        """
        if reintentos < 0:
            raise ValueError("reintentos no puede ser negativo")
        self.url_base = resolver_url_base(url_base if url_base is not None else os.environ.get("BINANCE_BASE_URL"))
        self._http = cliente_http or httpx.Client(timeout=httpx.Timeout(tiempo_respuesta, connect=tiempo_conexion))
        self._reintentos = reintentos
        self._pausa_reintento = pausa_reintento

    # ---------- FuenteDeMercado ----------

    def obtener_velas(self, simbolo: str, intervalo: Intervalo, cantidad: int) -> ListaDoble[Vela]:
        """Obtiene las ``cantidad`` velas más recientes, de la más antigua a la más reciente.

        Si se piden más de 1000, hace varias peticiones hacia atrás en el tiempo
        con ``endTime``: cada lote se recorre con ``iterador_atras()`` de la
        ListaDoble y se agrega al inicio del resultado, descartando las velas que
        ya estaban (duplicadas). Al paginar se pide una vela extra por si la
        fuente repite la del borde.
        Complejidad: O(cantidad) en memoria y procesamiento, más ⌈cantidad / 1000⌉ peticiones.

        Raises:
            ValueError: si el símbolo o la cantidad son inválidos.
            MercadoError: si Binance falla o entrega datos inválidos.
        """
        simbolo_normalizado = normalizar_simbolo(simbolo)
        if cantidad < 1:
            raise ValueError("La cantidad de velas debe ser al menos 1")

        resultado: ListaDoble[Vela] = ListaDoble()
        tiempo_final: int | None = None
        while resultado.tamanio() < cantidad:
            faltan = cantidad - resultado.tamanio() + (0 if tiempo_final is None else 1)
            limite = min(faltan, LIMITE_POR_PETICION)
            lote = self._pedir_klines(simbolo_normalizado, intervalo, limite, tiempo_final)
            validar_velas(lote)

            # El lote va de la más antigua a la más reciente; se recorre al revés
            # para ir agregando al inicio, y solo se aceptan velas más antiguas que
            # la primera que ya tenemos, así no entran duplicados.
            limite_superior = resultado.primero().tiempo_apertura if not resultado.esta_vacia() else None
            agregadas = 0
            for vela in lote.iterador_atras():
                if resultado.tamanio() >= cantidad:
                    break
                if limite_superior is None or vela.tiempo_apertura < limite_superior:
                    resultado.agregar_inicio(vela)
                    limite_superior = vela.tiempo_apertura
                    agregadas += 1
            if agregadas == 0 or lote.tamanio() < limite:
                break  # no hay más historial
            tiempo_final = resultado.primero().tiempo_apertura - 1
        validar_velas(resultado)
        return resultado

    def obtener_precio_actual(self, simbolo: str) -> float:
        """Obtiene el último precio negociado.

        Raises:
            ValueError: si el símbolo es inválido.
            MercadoError: si Binance falla o la respuesta no trae un precio positivo.
        """
        texto = self._pedir("/api/v3/ticker/price", {"symbol": normalizar_simbolo(simbolo)})
        raiz = _leer_json(texto, "precio")
        if not isinstance(raiz, dict) or "price" not in raiz:
            raise MercadoError("Respuesta de precio inválida: falta el campo 'price'")
        precio = _como_float(raiz["price"], "price")
        if not precio > 0 or precio == float("inf"):
            raise MercadoError("Respuesta de precio inválida: el precio debe ser positivo")
        return precio

    # ---------- ciclo de vida ----------

    def cerrar(self) -> None:
        """Cierra las conexiones HTTP."""
        self._http.close()

    def __enter__(self) -> ClienteBinance:
        return self

    def __exit__(
        self, tipo: type[BaseException] | None, error: BaseException | None, traza: TracebackType | None
    ) -> None:
        self.cerrar()

    # ---------- internos ----------

    def _pedir_klines(
        self, simbolo: str, intervalo: Intervalo, limite: int, tiempo_final: int | None
    ) -> ListaDoble[Vela]:
        parametros: dict[str, str | int] = {"symbol": simbolo, "interval": intervalo.codigo, "limit": limite}
        if tiempo_final is not None:
            parametros["endTime"] = tiempo_final
        return convertir_klines(self._pedir("/api/v3/klines", parametros))

    def _pedir(self, ruta: str, parametros: dict[str, str | int]) -> str:
        """GET que devuelve el cuerpo si la respuesta es 200, con reintentos ante fallos de red o 5xx."""
        ultimo_error: MercadoError | None = None
        for intento in range(self._reintentos + 1):
            if intento > 0 and self._pausa_reintento > 0:
                time.sleep(self._pausa_reintento)
            try:
                respuesta = self._http.get(self.url_base + ruta, params=parametros,
                                           headers={"Accept": "application/json"})
            except httpx.TimeoutException as e:
                ultimo_error = MercadoError("Binance no respondió a tiempo")
                ultimo_error.__cause__ = e
                continue
            except httpx.TransportError as e:
                ultimo_error = MercadoError(f"No se pudo conectar con Binance: {e}")
                ultimo_error.__cause__ = e
                continue
            if respuesta.status_code == 200:
                return respuesta.text
            ultimo_error = MercadoError(_mensaje_de_error(respuesta.status_code, respuesta.text))
            if respuesta.status_code < 500:
                raise ultimo_error
        assert ultimo_error is not None
        raise ultimo_error


def convertir_klines(texto: str) -> ListaDoble[Vela]:
    """Convierte el texto de una respuesta de ``/api/v3/klines`` en velas, en el mismo orden.

    No valida la coherencia de las velas (eso lo hace ``validar_velas``).
    Complejidad: O(n) en la longitud del texto.

    Raises:
        MercadoError: si el formato no es el esperado.
    """
    raiz = _leer_json(texto, "klines")
    if not isinstance(raiz, list):
        raise MercadoError("Respuesta de klines inválida: se esperaba un arreglo")
    velas: ListaDoble[Vela] = ListaDoble()
    # Borde de entrada: el módulo json entrega una list; las velas pasan enseguida a la ListaDoble.
    for indice, fila in enumerate(raiz):
        if not isinstance(fila, list) or len(fila) < 7:
            raise MercadoError(f"Respuesta de klines inválida: la vela {indice} no tiene al menos 7 campos")
        velas.agregar_final(Vela(
            tiempo_apertura=_como_int(fila[0], "tiempo_apertura"),
            apertura=_como_float(fila[1], "apertura"),
            maximo=_como_float(fila[2], "maximo"),
            minimo=_como_float(fila[3], "minimo"),
            cierre=_como_float(fila[4], "cierre"),
            volumen=_como_float(fila[5], "volumen"),
            tiempo_cierre=_como_int(fila[6], "tiempo_cierre"),
        ))
    return velas


def normalizar_simbolo(simbolo: str | None) -> str:
    """Pasa a mayúsculas y exige solo letras y dígitos (2 a 20), para no inyectar nada en la URL.

    Raises:
        ValueError: si el símbolo es inválido.
    """
    normalizado = (simbolo or "").strip().upper()
    if not _SIMBOLO_VALIDO.fullmatch(normalizado):
        raise ValueError(f"Símbolo inválido: {simbolo}")
    return normalizado


def resolver_url_base(valor: str | None) -> str:
    """La URL dada si no está vacía, o la de por defecto; sin barra final."""
    url = valor.strip() if valor and valor.strip() else URL_BASE_POR_DEFECTO
    return url.rstrip("/")


def _mensaje_de_error(codigo: int, cuerpo: str) -> str:
    """Mensaje claro, con el campo "msg" que Binance manda en sus errores si viene."""
    mensaje = f"Binance respondió HTTP {codigo}"
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        return mensaje  # el cuerpo no es JSON; basta con el código
    if isinstance(datos, dict) and isinstance(datos.get("msg"), str):
        return f"{mensaje}: {datos['msg']}"
    return mensaje


def _leer_json(texto: str, que: str) -> Any:
    try:
        return json.loads(texto)
    except ValueError as e:
        raise MercadoError(f"Respuesta de {que} no es JSON válido: {e}") from e


def _como_float(valor: object, campo: str) -> float:
    if isinstance(valor, int | float) and not isinstance(valor, bool):
        return float(valor)
    if isinstance(valor, str):
        try:
            return float(valor)
        except ValueError:
            pass
    raise MercadoError(f"Campo '{campo}' inválido en la respuesta de Binance: {valor!r}")


def _como_int(valor: object, campo: str) -> int:
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        try:
            return int(valor)
        except ValueError:
            pass
    raise MercadoError(f"Campo '{campo}' inválido en la respuesta de Binance: {valor!r}")
