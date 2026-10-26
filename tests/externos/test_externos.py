import time

import httpx
import pytest
from fastapi.testclient import TestClient

from bitcoinai.api import Configuracion, crear_app
from bitcoinai.externos import ClienteExternos, DatosExternos, FuenteExternaError, SeriesExternas, SerieTemporal
from bitcoinai.externos.servicio import movimiento_esperado, resolucion_dvol
from bitcoinai.ia.caracteristicas import NOMBRES, construir_conjunto
from bitcoinai.ia.servicio import ServicioIA
from bitcoinai.modelo import Intervalo
from tests.apoyo.fuente_falsa import INICIO, FuenteFalsa, generar_velas
from tests.externos.falsas import DIA, HORA, FuentesFalsas

AHORA = int(time.time() * 1000)


def falsas(caidas: tuple[str, ...] = ()) -> FuentesFalsas:
    return FuentesFalsas(INICIO - 60 * DIA, AHORA, caidas)


# ---------- la serie ----------


def test_valor_en_es_el_ultimo_ya_conocido() -> None:
    serie = SerieTemporal("x")
    for t, v in ((100, 1.0), (300, 3.0), (200, 2.0)):
        serie.agregar(t, v)
    assert [serie.valor_en(t) for t in (99, 100, 250, 300, 10_000)] == [None, 1.0, 2.0, 3.0, 3.0]
    assert serie.desde() == 100 and serie.ultimo() == (300, 3.0) and serie.tamanio() == 3


# ---------- los clientes ----------


def test_los_clientes_leen_las_tres_fuentes() -> None:
    f = falsas()
    cliente = f.cliente()
    fng, clasificacion = cliente.miedo_codicia()
    assert clasificacion == "Fear" and fng.desde() == INICIO - 60 * DIA
    financiacion = cliente.financiacion(INICIO - 60 * DIA, AHORA)
    assert financiacion.tamanio() > 1000  # necesitó varias páginas de 1000
    assert sum(1 for p in f.peticiones if "fundingRate" in str(p.url)) >= 2
    dvol = cliente.dvol(INICIO - 60 * DIA, AHORA, "1D")
    primero = dvol.desde()
    assert primero is not None and primero % DIA == 0 and primero >= INICIO - 59 * DIA
    assert cliente.largos_y_cortos() == pytest.approx(0.6902)


def test_el_dvol_pagina_hacia_atras_con_continuation() -> None:
    f = falsas()
    serie = f.cliente().dvol(AHORA - 1500 * HORA, AHORA, "3600")
    assert serie.tamanio() >= 1499
    assert sum(1 for p in f.peticiones if "volatility" in str(p.url)) == 2


def test_errores_de_las_fuentes() -> None:
    cliente = falsas(caidas=("alternative.me",)).cliente()
    with pytest.raises(FuenteExternaError, match="500"):
        cliente.miedo_codicia()
    raro = ClienteExternos(httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"x": 1}))))
    with pytest.raises(FuenteExternaError, match="otra forma"):
        raro.miedo_codicia()
    caido = ClienteExternos(httpx.Client(transport=httpx.MockTransport(lambda _: (_ for _ in ()).throw(
        httpx.ConnectError("sin red")))))
    with pytest.raises(FuenteExternaError, match="ConnectError"):
        caido.largos_y_cortos()


# ---------- características ----------


def test_las_fuentes_suman_caracteristicas_sin_mirar_el_futuro() -> None:
    velas = generar_velas(200, Intervalo.D1)
    series = DatosExternos(falsas().cliente()).series(INICIO, Intervalo.D1)
    conjunto = construir_conjunto(velas, series)
    assert conjunto.fuentes_usadas == ("miedo-codicia", "financiacion", "dvol")
    assert len(conjunto.nombres) == len(NOMBRES) + 6 and conjunto.nombres[10] == "Miedo y codicia"
    primera = conjunto.muestras.obtener(0)
    assert len(primera.caracteristicas) == 16
    # La vela 50 cierra al final de su día: usa el miedo y codicia publicado al empezar ese día, no el de mañana.
    vela = velas.obtener(50)
    assert series.miedo_codicia is not None
    esperado = series.miedo_codicia.valor_en(vela.tiempo_cierre)
    assert esperado is not None and primera.caracteristicas[10] == pytest.approx(esperado / 100)
    assert series.miedo_codicia.valor_en(vela.tiempo_cierre + DIA) != esperado  # el de mañana es otro
    assert conjunto.ultima is not None and len(conjunto.ultima) == 16


def test_una_fuente_sin_historial_suficiente_no_entra() -> None:
    velas = generar_velas(200, Intervalo.D1)
    corta = SerieTemporal("DVOL")
    corta.agregar(INICIO + 150 * DIA, 50.0)  # empieza a mitad de las velas
    conjunto = construir_conjunto(velas, SeriesExternas(None, None, corta, {"miedo-codicia": "Respondió 500"}))
    assert conjunto.fuentes_usadas == ()
    assert conjunto.nombres == NOMBRES
    assert conjunto.fuentes_omitidas == {"miedo-codicia": "Respondió 500", "financiacion": "No respondió",
                                         "dvol": "Su historial no alcanza a cubrir todas las velas"}


def test_resolucion_y_movimiento_esperado() -> None:
    assert [resolucion_dvol(i) for i in (Intervalo.M15, Intervalo.H1, Intervalo.H4, Intervalo.D1)] == [
        "3600", "3600", "43200", "1D"]
    assert movimiento_esperado(40, 3600) == pytest.approx(0.004272, rel=1e-3)


# ---------- servicio e API ----------


def test_la_ia_aprende_con_las_fuentes_y_compara_con_y_sin_ellas() -> None:
    externos = DatosExternos(falsas().cliente())
    p = ServicioIA(FuenteFalsa(), "BTCUSDT", externos=externos).predecir(Intervalo.D1)
    assert p.fuentes_usadas == ("miedo-codicia", "financiacion", "dvol") and p.fuentes_omitidas == {}
    assert len(p.caracteristicas) == len(p.nombres) == 16
    assert p.comparacion is not None and p.comparacion.sin_externos.muestras == p.comparacion.con_externos.muestras


def test_si_las_fuentes_fallan_la_ia_sigue_solo_con_el_precio() -> None:
    externos = DatosExternos(falsas(caidas=("alternative.me", "fundingRate", "get_volatility_index_data")).cliente())
    p = ServicioIA(FuenteFalsa(), "BTCUSDT", externos=externos).predecir(Intervalo.D1)
    assert p.fuentes_usadas == () and p.comparacion is None and p.nombres == NOMBRES
    assert set(p.fuentes_omitidas) == {"miedo-codicia", "financiacion", "dvol"}


def test_la_cache_no_vuelve_a_pedir() -> None:
    f = falsas()
    externos = DatosExternos(f.cliente())
    externos.series(INICIO, Intervalo.D1)
    antes = len(f.peticiones)
    externos.series(INICIO + DIA, Intervalo.D1)  # pide menos historia: lo guardado alcanza
    assert len(f.peticiones) == antes


def test_api_con_fuentes_externas() -> None:
    externos = DatosExternos(falsas(caidas=("globalLongShortAccountRatio",)).cliente())
    cliente = TestClient(crear_app(Configuracion(), FuenteFalsa(precio=80_000), externos=externos))
    p = cliente.get("/api/ia/predicciones", params={"intervalo": "1d"}).json()
    usadas = p["fuentesExternas"]["usadas"]
    assert [f["id"] for f in usadas] == ["miedo-codicia", "financiacion", "dvol"]
    assert usadas[0]["nombre"] == "Índice de miedo y codicia"
    comparacion = p["fuentesExternas"]["comparacion"]
    assert set(comparacion) == {"sinExternos", "conExternos", "conclusion"} and "fuentes externas" in comparacion[
        "conclusion"]
    assert len(p["caracteristicas"]) == 16

    f = cliente.get("/api/ia/fuentes", params={"intervalo": "1h"}).json()
    ids = [lec["id"] for lec in f["lecturas"]]
    assert ids == ["miedo-codicia", "financiacion", "dvol"]  # la de largos y cortos se cayó
    assert f["errores"] == [{"id": "largos", "motivo": "Respondió 500"}]
    dvol = f["lecturas"][2]
    assert dvol["valorTexto"].endswith("por vela") and "USDT" in dvol["explicacion"]
    assert "miedo" in f["lecturas"][0]["explicacion"]
    assert cliente.get("/api/ia/fuentes", params={"intervalo": "2h"}).status_code == 400


def test_sin_fuentes_externas_la_ruta_responde_vacio() -> None:
    cliente = TestClient(crear_app(Configuracion(), FuenteFalsa()))
    assert cliente.get("/api/ia/fuentes").json() == {"lecturas": [], "errores": [], "actualizadoEn": None}
