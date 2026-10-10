"""Pruebas del cliente de Binance contra un transporte falso de httpx: no usan internet."""

from collections.abc import Callable

import httpx
import pytest

from bitcoinai.estructuras import ListaDoble
from bitcoinai.mercado import (
    MENSAJE_REGION_RESTRINGIDA,
    ClienteBinance,
    MercadoError,
    convertir_klines,
    resolver_url_base,
)
from bitcoinai.modelo import Intervalo, Vela

DIA = Intervalo.D1.milisegundos
INICIO = 1_600_000_000_000

Manejador = Callable[[httpx.Request], httpx.Response]


class BinanceFalso:
    """Transporte que imita a Binance y anota cada petición."""

    def __init__(self, manejador: Manejador) -> None:
        self.manejador = manejador
        self.peticiones: tuple[httpx.Request, ...] = ()

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones += (peticion,)
        return self.manejador(peticion)

    def cliente(self, reintentos: int = 1) -> ClienteBinance:
        http = httpx.Client(transport=httpx.MockTransport(self))
        return ClienteBinance("http://binance.falso", cliente_http=http, reintentos=reintentos, pausa_reintento=0)

    @property
    def ultima(self) -> httpx.Request:
        return self.peticiones[-1]


def historial(total: int, solapar: bool = False) -> Manejador:
    """Imita /api/v3/klines con ``total`` velas diarias: devuelve las últimas ``limit``
    con apertura <= endTime. Con ``solapar`` incluye además una vela posterior a endTime,
    para comprobar que el cliente descarta duplicados."""

    def manejar(peticion: httpx.Request) -> httpx.Response:
        limite = int(peticion.url.params["limit"])
        ultimo = total - 1
        if "endTime" in peticion.url.params:
            ultimo = min(total - 1, (int(peticion.url.params["endTime"]) - INICIO) // DIA)
            if solapar:
                ultimo = min(total - 1, ultimo + 1)
        primero = max(0, ultimo - limite + 1)
        filas = ",".join(
            f'[{INICIO + i * DIA},"{100 + i}","{105 + i}","{95 + i}","{101 + i}","10.0",'
            f'{INICIO + (i + 1) * DIA - 1},"0",1,"0","0","0"]'
            for i in range(primero, ultimo + 1)
        )
        return httpx.Response(200, text=f"[{filas}]")

    return manejar


def assert_consecutivas(velas: ListaDoble[Vela]) -> None:
    anterior: Vela | None = None
    for v in velas:
        if anterior is not None:
            assert v.tiempo_apertura == anterior.tiempo_apertura + DIA
        anterior = v


# ---------- conversión de klines ----------


def test_convierte_una_respuesta_de_klines_escrita_a_mano() -> None:
    texto = """
    [
      [1499040000000, "0.01634790", "0.80000000", "0.01575800", "0.01577100",
       "148976.11427815", 1499644799999, "2434.19055334", 308, "1756.87402397",
       "28.46694368", "0"],
      [1499644800000, "0.01577100", "0.02000000", "0.01500000", "0.01900000",
       "1000.5", 1500249599999, "20.0", 10, "500.0", "9.0", "0"]
    ]
    """
    velas = convertir_klines(texto)
    assert velas.tamanio() == 2
    assert velas.primero() == Vela(1499040000000, 0.01634790, 0.80000000, 0.01575800, 0.01577100,
                                   148976.11427815, 1499644799999)
    assert velas.ultimo().tiempo_apertura == 1499644800000
    assert velas.ultimo().cierre == 0.019
    assert velas.ultimo().tiempo_cierre == 1500249599999


@pytest.mark.parametrize("texto", ["{}", '[[1, "2", "3"]]', '[[1, "abc", "3", "1", "2", "5", 9]]',
                                   "no es json", '[[true, "1", "1", "1", "1", "1", 2]]'])
def test_convertir_klines_rechaza_formatos_invalidos(texto: str) -> None:
    with pytest.raises(MercadoError):
        convertir_klines(texto)


def test_convertir_klines_acepta_arreglo_vacio() -> None:
    assert convertir_klines("[]").tamanio() == 0


# ---------- velas ----------


def test_pocas_velas_se_piden_en_una_sola_peticion() -> None:
    binance = BinanceFalso(historial(50))
    velas = binance.cliente().obtener_velas("btcusdt", Intervalo.D1, 10)

    assert velas.tamanio() == 10
    assert len(binance.peticiones) == 1
    assert binance.ultima.url.path == "/api/v3/klines"
    assert dict(binance.ultima.url.params) == {"symbol": "BTCUSDT", "interval": "1d", "limit": "10"}
    assert velas.primero().tiempo_apertura == INICIO + 40 * DIA
    assert velas.ultimo().tiempo_apertura == INICIO + 49 * DIA


def test_mas_de_mil_velas_se_paginan_hacia_atras_sin_duplicados() -> None:
    binance = BinanceFalso(historial(2500))
    velas = binance.cliente().obtener_velas("BTCUSDT", Intervalo.D1, 2300)

    assert velas.tamanio() == 2300
    assert len(binance.peticiones) == 3  # 1000 + 1000 + 300
    assert velas.primero().tiempo_apertura == INICIO + 200 * DIA
    assert velas.ultimo().tiempo_apertura == INICIO + 2499 * DIA
    assert_consecutivas(velas)


def test_si_la_fuente_devuelve_velas_solapadas_se_descartan_los_duplicados() -> None:
    binance = BinanceFalso(historial(3000, solapar=True))
    velas = binance.cliente().obtener_velas("BTCUSDT", Intervalo.D1, 2500)

    assert velas.tamanio() == 2500
    assert velas.ultimo().tiempo_apertura == INICIO + 2999 * DIA
    assert_consecutivas(velas)


def test_si_no_hay_tanto_historial_devuelve_lo_que_existe() -> None:
    binance = BinanceFalso(historial(1500))
    velas = binance.cliente().obtener_velas("BTCUSDT", Intervalo.D1, 3000)

    assert velas.tamanio() == 1500
    assert len(binance.peticiones) == 2
    assert velas.primero().tiempo_apertura == INICIO
    assert_consecutivas(velas)


def test_velas_incoherentes_de_la_fuente_lanzan_mercado_error() -> None:
    # máximo (5) menor que mínimo (9)
    binance = BinanceFalso(lambda p: httpx.Response(200, text='[[1000, "6", "5", "9", "7", "1", 1999]]'))
    with pytest.raises(MercadoError):
        binance.cliente().obtener_velas("BTCUSDT", Intervalo.D1, 1)


def test_parametros_invalidos_no_hacen_peticiones() -> None:
    binance = BinanceFalso(historial(10))
    cliente = binance.cliente()
    with pytest.raises(ValueError):
        cliente.obtener_velas("BTCUSDT", Intervalo.D1, 0)
    with pytest.raises(ValueError):
        cliente.obtener_velas("BTC/USDT&x=1", Intervalo.D1, 5)
    with pytest.raises(ValueError):
        cliente.obtener_precio_actual(" ")
    assert binance.peticiones == ()


# ---------- precio ----------


def test_obtiene_precio_actual() -> None:
    binance = BinanceFalso(lambda p: httpx.Response(200, text='{"symbol":"BTCUSDT","price":"67123.45000000"}'))
    assert binance.cliente().obtener_precio_actual("BTCUSDT") == 67123.45
    assert binance.ultima.url.path == "/api/v3/ticker/price"
    assert dict(binance.ultima.url.params) == {"symbol": "BTCUSDT"}


@pytest.mark.parametrize("cuerpo", ['{"symbol":"BTCUSDT"}', '{"price":"0"}', '{"price":"-1"}', "[1]"])
def test_precio_sin_campo_price_o_invalido_lanza(cuerpo: str) -> None:
    binance = BinanceFalso(lambda p: httpx.Response(200, text=cuerpo))
    with pytest.raises(MercadoError):
        binance.cliente().obtener_precio_actual("BTCUSDT")


# ---------- errores y reintentos ----------


def test_error_4xx_incluye_el_mensaje_de_binance_y_no_se_reintenta() -> None:
    binance = BinanceFalso(lambda p: httpx.Response(400, text='{"code":-1121,"msg":"Invalid symbol."}'))
    with pytest.raises(MercadoError) as error:
        binance.cliente().obtener_velas("NOEXISTE", Intervalo.D1, 5)
    assert str(error.value) == "Binance respondió HTTP 400: Invalid symbol."
    assert len(binance.peticiones) == 1


def test_error_451_explica_la_region_restringida_y_lo_registra(caplog: pytest.LogCaptureFixture) -> None:
    cuerpo = '{"code":0,"msg":"Service unavailable from a restricted location"}'
    binance = BinanceFalso(lambda p: httpx.Response(451, text=cuerpo))
    with pytest.raises(MercadoError) as error:
        binance.cliente().obtener_precio_actual("BTCUSDT")
    assert str(error.value) == MENSAJE_REGION_RESTRINGIDA
    assert MENSAJE_REGION_RESTRINGIDA.startswith("Binance no está disponible desde esta región")
    assert len(binance.peticiones) == 1  # reintentar no sirve
    assert "HTTP 451 desde http://binance.falso" in caplog.text


def test_error_5xx_se_reintenta_una_vez_y_si_funciona_devuelve_el_dato() -> None:
    def manejar(peticion: httpx.Request) -> httpx.Response:
        if len(binance.peticiones) == 1:
            return httpx.Response(503, text="Servicio no disponible")
        return httpx.Response(200, text='{"price":"100.5"}')

    binance = BinanceFalso(manejar)
    assert binance.cliente().obtener_precio_actual("BTCUSDT") == 100.5
    assert len(binance.peticiones) == 2


def test_error_5xx_persistente_lanza_despues_del_reintento() -> None:
    binance = BinanceFalso(lambda p: httpx.Response(500, text="error interno"))
    with pytest.raises(MercadoError) as error:
        binance.cliente().obtener_precio_actual("BTCUSDT")
    assert str(error.value) == "Binance respondió HTTP 500"
    assert len(binance.peticiones) == 2


def test_respuesta_lenta_agota_el_tiempo_de_espera() -> None:
    def manejar(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("tardó demasiado", request=peticion)

    binance = BinanceFalso(manejar)
    with pytest.raises(MercadoError) as error:
        binance.cliente().obtener_precio_actual("BTCUSDT")
    assert str(error.value) == "Binance no respondió a tiempo"
    assert len(binance.peticiones) == 2


def test_sin_conexion_lanza_error_de_conexion() -> None:
    def manejar(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexión rechazada", request=peticion)

    binance = BinanceFalso(manejar)
    with pytest.raises(MercadoError) as error:
        binance.cliente(reintentos=0).obtener_precio_actual("BTCUSDT")
    assert str(error.value).startswith("No se pudo conectar con Binance")
    assert len(binance.peticiones) == 1


# ---------- configuración ----------


def test_resolver_url_base_usa_el_valor_por_defecto_y_quita_la_barra_final() -> None:
    assert resolver_url_base(None) == "https://api.binance.com"
    assert resolver_url_base("  ") == "https://api.binance.com"
    assert resolver_url_base(" https://api.binance.us/ ") == "https://api.binance.us"
    assert ClienteBinance("https://data-api.binance.vision/").url_base == "https://data-api.binance.vision"


def test_la_url_base_sale_de_la_variable_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BINANCE_BASE_URL", "https://data-api.binance.vision")
    with ClienteBinance() as cliente:
        assert cliente.url_base == "https://data-api.binance.vision"
    monkeypatch.delenv("BINANCE_BASE_URL")
    assert ClienteBinance().url_base == "https://api.binance.com"


def test_reintentos_negativos_son_invalidos() -> None:
    with pytest.raises(ValueError):
        ClienteBinance(reintentos=-1)
