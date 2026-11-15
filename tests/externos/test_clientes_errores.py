"""Los rechazos de las fuentes externas.

Una fuente pública puede responder cualquier cosa: un 200 con HTML, una lista vacía o un
JSON con otra forma. El cliente debe convertir todo eso en ``FuenteExternaError`` con un
mensaje entendible, nunca en un ``KeyError`` ni en un dato a medias.
"""

import httpx
import pytest

from bitcoinai.externos import ClienteExternos, FuenteExternaError

DESDE = 1_700_000_000_000
HASTA = DESDE + 7 * 24 * 3_600_000


def cliente_que_responde(cuerpo: object = None, texto: str | None = None) -> ClienteExternos:
    def responder(_: httpx.Request) -> httpx.Response:
        if texto is not None:
            return httpx.Response(200, text=texto)
        return httpx.Response(200, json=cuerpo)

    return ClienteExternos(httpx.Client(transport=httpx.MockTransport(responder)))


def test_una_respuesta_que_no_es_json() -> None:
    with pytest.raises(FuenteExternaError, match="no es JSON"):
        cliente_que_responde(texto="<html>mantenimiento</html>").miedo_codicia()


def test_el_indice_llega_vacio() -> None:
    with pytest.raises(FuenteExternaError, match="llegó vacío"):
        cliente_que_responde({"data": []}).miedo_codicia()


def test_el_indice_con_columnas_cambiadas() -> None:
    with pytest.raises(FuenteExternaError, match="otra forma"):
        cliente_que_responde({"data": [{"fecha": 1, "valor": "x"}]}).miedo_codicia()


def test_la_financiacion_no_es_una_lista() -> None:
    with pytest.raises(FuenteExternaError, match="otra forma"):
        cliente_que_responde({"codigo": -1}).financiacion(DESDE, HASTA)


def test_la_financiacion_con_filas_rotas() -> None:
    with pytest.raises(FuenteExternaError, match="otra forma"):
        cliente_que_responde([{"fundingTime": "ayer", "fundingRate": None}]).financiacion(DESDE, HASTA)


def test_no_llegaron_tasas_de_financiacion() -> None:
    with pytest.raises(FuenteExternaError, match="No llegaron tasas"):
        cliente_que_responde([]).financiacion(DESDE, HASTA)


def test_la_financiacion_para_cuando_la_pagina_es_corta() -> None:
    serie = cliente_que_responde([{"fundingTime": DESDE, "fundingRate": "0.0001"}]).financiacion(DESDE, HASTA)
    assert serie.tamanio() == 1 and serie.ultimo() == (DESDE, 0.0001)


def test_largos_y_cortos_con_otra_forma() -> None:
    with pytest.raises(FuenteExternaError, match="otra forma"):
        cliente_que_responde({"no": "es una lista"}).largos_y_cortos()
    with pytest.raises(FuenteExternaError, match="otra forma"):
        cliente_que_responde([]).largos_y_cortos()


def test_el_dvol_con_filas_rotas() -> None:
    with pytest.raises(FuenteExternaError, match="otra forma"):
        cliente_que_responde({"result": {"data": [{"inicio": 1}], "continuation": None}}).dvol(DESDE, HASTA, "1D")


def test_el_dvol_llega_vacio() -> None:
    with pytest.raises(FuenteExternaError, match="No llegó el DVOL"):
        cliente_que_responde({"result": {"data": [], "continuation": None}}).dvol(DESDE, HASTA, "1D")


def test_el_dvol_cierra_con_el_cierre_del_periodo() -> None:
    cuerpo = {"result": {"data": [[DESDE, 50.0, 60.0, 40.0, 55.5]], "continuation": None}}
    serie = cliente_que_responde(cuerpo).dvol(DESDE, HASTA, "1D")
    assert serie.tamanio() == 1
    assert serie.ultimo() == (DESDE + 24 * 3_600_000, 55.5)  # el cierre se conoce al terminar el día
