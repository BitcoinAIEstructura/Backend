import pytest

from bitcoinai.mercado import CacheMercado, MercadoError
from bitcoinai.modelo import Intervalo
from tests.apoyo.fuente_falsa import FuenteFalsa


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1.0

    def __call__(self) -> float:
        return self.ahora


@pytest.fixture
def fuente() -> FuenteFalsa:
    return FuenteFalsa()


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def cache(fuente: FuenteFalsa, reloj: Reloj) -> CacheMercado:
    return CacheMercado(fuente, 30, reloj)


def test_segunda_llamada_dentro_del_ttl_no_consulta_la_fuente(cache: CacheMercado, fuente: FuenteFalsa,
                                                                reloj: Reloj) -> None:
    primera = cache.obtener_velas("BTCUSDT", Intervalo.D1, 10)
    reloj.ahora += 29.999
    segunda = cache.obtener_velas("BTCUSDT", Intervalo.D1, 10)
    assert fuente.llamadas_velas == 1
    assert segunda.tamanio() == 10
    assert primera.ultimo() == segunda.ultimo()


def test_despues_del_ttl_vuelve_a_consultar_la_fuente(cache: CacheMercado, fuente: FuenteFalsa, reloj: Reloj) -> None:
    cache.obtener_velas("BTCUSDT", Intervalo.D1, 10)
    reloj.ahora += 30
    cache.obtener_velas("BTCUSDT", Intervalo.D1, 10)
    assert fuente.llamadas_velas == 2


def test_parametros_distintos_se_guardan_por_separado(cache: CacheMercado, fuente: FuenteFalsa) -> None:
    cache.obtener_velas("BTCUSDT", Intervalo.D1, 10)
    cache.obtener_velas("BTCUSDT", Intervalo.D1, 20)
    cache.obtener_velas("BTCUSDT", Intervalo.H1, 10)
    cache.obtener_velas("ETHUSDT", Intervalo.D1, 10)
    cache.obtener_velas("BTCUSDT", Intervalo.D1, 20)
    assert fuente.llamadas_velas == 4


def test_el_precio_tambien_se_guarda(cache: CacheMercado, fuente: FuenteFalsa, reloj: Reloj) -> None:
    assert cache.obtener_precio_actual("BTCUSDT") == 100.0
    fuente.precio = 200.0
    assert cache.obtener_precio_actual("BTCUSDT") == 100.0
    assert fuente.llamadas_precio == 1
    reloj.ahora += 30
    assert cache.obtener_precio_actual("BTCUSDT") == 200.0


def test_los_errores_no_se_guardan(cache: CacheMercado, fuente: FuenteFalsa) -> None:
    fuente.error = MercadoError("caída")
    with pytest.raises(MercadoError):
        cache.obtener_velas("BTCUSDT", Intervalo.D1, 5)
    fuente.error = None
    assert cache.obtener_velas("BTCUSDT", Intervalo.D1, 5).tamanio() == 5
    assert fuente.llamadas_velas == 2


def test_modificar_la_lista_devuelta_no_dania_la_cache(cache: CacheMercado, fuente: FuenteFalsa) -> None:
    cache.obtener_velas("BTCUSDT", Intervalo.D1, 10).vaciar()
    assert cache.obtener_velas("BTCUSDT", Intervalo.D1, 10).tamanio() == 10
    assert fuente.llamadas_velas == 1


def test_ttl_cero_desactiva_la_cache(fuente: FuenteFalsa, reloj: Reloj) -> None:
    sin_cache = CacheMercado(fuente, 0, reloj)
    sin_cache.obtener_precio_actual("BTCUSDT")
    sin_cache.obtener_precio_actual("BTCUSDT")
    assert fuente.llamadas_precio == 2


def test_ttl_negativo_es_invalido(fuente: FuenteFalsa) -> None:
    with pytest.raises(ValueError):
        CacheMercado(fuente, -1)
