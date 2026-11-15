"""GET /api/exportar/ordenes: el historial de órdenes en CSV, para abrirlo en una hoja de cálculo.

El archivo se descarga (``Content-Disposition: attachment``), empieza con BOM para que
Excel muestre bien los acentos, y escapa las celdas que traen comas, comillas o saltos de
línea. También neutraliza los textos que una hoja de cálculo interpretaría como fórmula.
"""

import csv
from collections.abc import Iterator
from typing import Protocol

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.simulacion import GestorSimulaciones
from tests.api.test_simulacion_api import post, registrado
from tests.apoyo.fuente_falsa import FuenteFalsa
from tests.usuarios.entorno import crear_entorno

COLUMNAS = ("id,tipo,estado,monto,todo,creadaEn,ejecutadaEn,precioEjecucion,cantidadBtc,comision,"
            "motivo,detalle")


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa()


@pytest.fixture
def gestor(fuente: FuenteFalsa) -> Iterator[GestorSimulaciones]:
    g = GestorSimulaciones(fuente, "BTCUSDT")
    yield g
    g.detener_todos()


@pytest.fixture
def app(fuente: FuenteFalsa, gestor: GestorSimulaciones) -> FastAPI:
    return crear_app(Configuracion(), fuente, cuentas=crear_entorno().servicio, gestor=gestor)


class RespuestaConCuerpo(Protocol):
    """Lo que necesita ``lineas``: el cuerpo en bytes (sirve el Response de TestClient)."""

    @property
    def content(self) -> bytes:
        """El cuerpo de la respuesta, en bytes."""


def lineas(respuesta: RespuestaConCuerpo) -> list[str]:
    return respuesta.content.decode("utf-8-sig").splitlines()


def test_exige_sesion(app: FastAPI) -> None:
    assert TestClient(app).get("/api/exportar/ordenes").status_code == 401


def test_es_un_archivo_csv_descargable(app: FastAPI) -> None:
    c = registrado(app)
    r = c.get("/api/exportar/ordenes")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="ordenes.csv"'


def test_sin_ordenes_solo_va_la_cabecera(app: FastAPI) -> None:
    c = registrado(app)
    assert lineas(c.get("/api/exportar/ordenes")) == [COLUMNAS]


def test_empieza_con_bom_para_que_excel_respete_los_acentos(app: FastAPI) -> None:
    c = registrado(app)
    assert c.get("/api/exportar/ordenes").content.startswith(b"\xef\xbb\xbf")


def test_exporta_las_ordenes_con_sus_datos(app: FastAPI) -> None:
    c = registrado(app)
    assert post(c, "/api/ordenes", '{"tipo":"COMPRA","monto":500}').status_code == 201

    filas = lineas(c.get("/api/exportar/ordenes"))
    assert filas[0] == COLUMNAS
    assert len(filas) == 2
    campos = filas[1].split(",")
    assert campos[0] == "1"  # id
    assert campos[1] == "COMPRA"
    assert campos[2] == "PENDIENTE"
    assert campos[3] == "500.0"  # monto
    assert campos[4] == "false"  # todo
    assert campos[10] == "manual"  # motivo


def test_escapa_comas_comillas_y_saltos_de_linea(app: FastAPI) -> None:
    c = registrado(app)
    motivo = 'dice "hola", y adiós'
    post(c, "/api/ordenes", '{"tipo":"COMPRA","monto":100,"motivo":"dice \\"hola\\", y adiós"}')

    crudo = lineas(c.get("/api/exportar/ordenes"))[1]
    assert '"dice ""hola"", y adiós"' in crudo  # comillas dobles: así lo exige el formato CSV
    fila = list(csv.reader([crudo]))[0]
    assert fila[10] == motivo  # al leerlo, vuelve el texto original intacto


@pytest.mark.parametrize("peligroso", ["=SUM(A1:A9)", "+1+1", "-2+3", "@SUMA(A1)"])
def test_neutraliza_los_textos_que_parecen_formula(app: FastAPI, peligroso: str) -> None:
    c = registrado(app)
    cuerpo = f'{{"tipo":"COMPRA","monto":100,"motivo":"{peligroso}"}}'
    assert post(c, "/api/ordenes", cuerpo).status_code == 201

    fila = lineas(c.get("/api/exportar/ordenes"))[1]
    assert f"'{peligroso}" in fila  # se antepone un apóstrofo: la hoja lo trata como texto


def test_cada_usuario_exporta_solo_lo_suyo(app: FastAPI) -> None:
    ana = registrado(app)
    beto = registrado(app, "beto@correo.co", "1098765432")
    post(ana, "/api/ordenes", '{"tipo":"COMPRA","monto":500}')
    post(beto, "/api/ordenes", '{"tipo":"COMPRA","monto":7}')

    filas_ana = lineas(ana.get("/api/exportar/ordenes"))
    filas_beto = lineas(beto.get("/api/exportar/ordenes"))
    assert len(filas_ana) == len(filas_beto) == 2
    assert ",500.0," in filas_ana[1]
    assert ",7.0," in filas_beto[1]
