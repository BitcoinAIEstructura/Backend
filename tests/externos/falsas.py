"""Las tres fuentes externas imitadas con httpx.MockTransport: no usan internet."""

import json
from collections.abc import Callable

import httpx

from bitcoinai.externos import ClienteExternos

HORA = 3_600_000
DIA = 24 * HORA


class FuentesFalsas:
    """Datos sintéticos desde ``desde`` hasta ``hasta`` (ms). ``caidas`` son las fuentes que responden 500."""

    def __init__(self, desde: int, hasta: int, caidas: tuple[str, ...] = ()) -> None:
        self.desde, self.hasta, self.caidas = desde, hasta, caidas
        self.peticiones: list[httpx.Request] = []

    def _fng(self) -> httpx.Response:
        dias = range((self.hasta - self.desde) // DIA + 1)
        datos = [{"value": str(20 + d % 60), "value_classification": "Fear",
                  "timestamp": str((self.desde + d * DIA) // 1000)} for d in dias]
        datos.reverse()  # alternative.me entrega del más nuevo al más viejo
        return httpx.Response(200, json={"name": "Fear and Greed Index", "data": datos})

    def _financiacion(self, peticion: httpx.Request) -> httpx.Response:
        inicio = int(peticion.url.params["startTime"])
        limite = int(peticion.url.params["limit"])
        filas = [{"fundingTime": t, "fundingRate": "0.0001" if (t // (8 * HORA)) % 2 else "-0.00005"}
                 for t in range(self.desde - self.desde % (8 * HORA), self.hasta, 8 * HORA) if t >= inicio]
        return httpx.Response(200, json=filas[:limite])

    def _dvol(self, peticion: httpx.Request) -> httpx.Response:
        resolucion = peticion.url.params["resolution"]
        paso = {"3600": HORA, "43200": 12 * HORA, "1D": DIA}[resolucion]
        inicio, fin = int(peticion.url.params["start_timestamp"]), int(peticion.url.params["end_timestamp"])
        filas = [[t, 50, 51, 49, 40 + (t // paso) % 10] for t in range(self.desde - self.desde % paso, self.hasta, paso)
                 if inicio <= t <= fin]
        siguiente = None
        if len(filas) > 1000:
            siguiente = filas[-1000][0] - 1
            filas = filas[-1000:]
        return httpx.Response(200, json={"jsonrpc": "2.0", "result": {"data": filas, "continuation": siguiente}})

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        url = str(peticion.url)
        rutas: dict[str, Callable[[], httpx.Response]] = {
            "alternative.me": self._fng,
            "fundingRate": lambda: self._financiacion(peticion),
            "globalLongShortAccountRatio": lambda: httpx.Response(200, json=[{"longAccount": "0.6902"}]),
            "get_volatility_index_data": lambda: self._dvol(peticion),
        }
        for clave, responder in rutas.items():
            if clave in url:
                if clave in self.caidas:
                    return httpx.Response(500, text="caído")
                return responder()
        return httpx.Response(404, content=json.dumps({"error": "no"}).encode())

    def cliente(self) -> ClienteExternos:
        return ClienteExternos(httpx.Client(transport=httpx.MockTransport(self)))
