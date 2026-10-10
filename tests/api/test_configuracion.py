import pytest

from bitcoinai.api import Configuracion


def test_valores_por_defecto() -> None:
    c = Configuracion.desde_entorno({})
    assert c.puerto == 8080
    assert c.url_base_binance == "https://api.binance.com"
    assert c.origen_permitido == "*"
    assert c.ttl_cache_segundos == 30
    assert c.simbolo == "BTCUSDT"
    assert c.max_streams == 50
    assert c.max_bots == 20
    assert c.data_dir == "./data"
    assert c.ruta_base_datos == "./data/bitcoinai.db"
    assert (c.cookie_segura, c.confiar_proxy) == (False, False)


def test_lee_las_variables_definidas() -> None:
    c = Configuracion.desde_entorno({
        "PORT": "3000",
        "BINANCE_BASE_URL": "https://data-api.binance.vision",
        "ORIGEN_PERMITIDO": "https://mi-panel.app",
        "TTL_CACHE_SEGUNDOS": "0",
        "SIMBOLO": " ethusdt ",
        "MAX_STREAMS": "5",
        "DATA_DIR": "/data",
    })
    assert c.puerto == 3000
    assert c.url_base_binance == "https://data-api.binance.vision"
    assert c.origen_permitido == "https://mi-panel.app"
    assert c.ttl_cache_segundos == 0
    assert c.simbolo == "ETHUSDT"
    assert c.max_streams == 5
    assert c.data_dir == "/data"


def test_valores_vacios_usan_el_por_defecto() -> None:
    c = Configuracion.desde_entorno({"PORT": " ", "ORIGEN_PERMITIDO": ""})
    assert c.puerto == 8080
    assert c.origen_permitido == "*"


def test_lee_del_entorno_real_si_no_se_pasa_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9191")
    assert Configuracion.desde_entorno().puerto == 9191


def test_puerto_invalido_da_un_mensaje_claro() -> None:
    with pytest.raises(ValueError, match=r"^PORT debe ser un número entero entre 0 y 65535: abc$"):
        Configuracion.desde_entorno({"PORT": "abc"})
    with pytest.raises(ValueError):
        Configuracion.desde_entorno({"PORT": "70000"})
    with pytest.raises(ValueError):
        Configuracion.desde_entorno({"PORT": "-1"})


def test_ttl_y_simbolo_invalidos() -> None:
    with pytest.raises(ValueError, match="TTL_CACHE_SEGUNDOS"):
        Configuracion.desde_entorno({"TTL_CACHE_SEGUNDOS": "-5"})
    with pytest.raises(ValueError, match="SIMBOLO inválido"):
        Configuracion.desde_entorno({"SIMBOLO": "BTC/USDT"})


def test_max_streams_fuera_de_rango() -> None:
    for valor in ("0", "10001", "muchos"):
        with pytest.raises(ValueError, match="MAX_STREAMS debe ser un número entero entre 1 y 10000"):
            Configuracion.desde_entorno({"MAX_STREAMS": valor})


def test_base_de_datos_cookie_y_proxy() -> None:
    c = Configuracion.desde_entorno({"DATA_DIR": "/data/", "COOKIE_SEGURA": "true", "CONFIAR_PROXY": "1"})
    assert c.ruta_base_datos == "/data/bitcoinai.db"
    assert (c.cookie_segura, c.confiar_proxy) == (True, True)
    assert Configuracion.desde_entorno({"BASE_DATOS": "otra.db"}).ruta_base_datos == "otra.db"
    with pytest.raises(ValueError, match="COOKIE_SEGURA debe ser true o false"):
        Configuracion.desde_entorno({"COOKIE_SEGURA": "quizas"})


def test_max_bots() -> None:
    assert Configuracion.desde_entorno({"MAX_BOTS": "3"}).max_bots == 3
    with pytest.raises(ValueError, match="MAX_BOTS debe ser un número entero entre 1 y 1000"):
        Configuracion.desde_entorno({"MAX_BOTS": "0"})
