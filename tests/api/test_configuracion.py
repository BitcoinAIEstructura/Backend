import pytest

from bitcoinai.api import Configuracion


def test_valores_por_defecto() -> None:
    c = Configuracion.desde_entorno({})
    assert c.puerto == 8080
    assert c.url_base_binance == "https://api.binance.com"
    assert c.origen_permitido == "*"
    assert c.ttl_cache_segundos == 30
    assert c.simbolo == "BTCUSDT"


def test_lee_las_variables_definidas() -> None:
    c = Configuracion.desde_entorno({
        "PORT": "3000",
        "BINANCE_BASE_URL": "https://data-api.binance.vision",
        "ORIGEN_PERMITIDO": "https://mi-panel.app",
        "TTL_CACHE_SEGUNDOS": "0",
        "SIMBOLO": " ethusdt ",
    })
    assert c.puerto == 3000
    assert c.url_base_binance == "https://data-api.binance.vision"
    assert c.origen_permitido == "https://mi-panel.app"
    assert c.ttl_cache_segundos == 0
    assert c.simbolo == "ETHUSDT"


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

