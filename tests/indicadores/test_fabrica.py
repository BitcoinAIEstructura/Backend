import pytest

from bitcoinai.indicadores import NOMBRES, BandasBollinger, Ema, Macd, Rsi, Sma, Volatilidad, crear_indicador
from tests.indicadores.velas_prueba import lineales


def assert_invalido(fragmento: str, nombre: str | None, parametros: dict[str, str]) -> None:
    with pytest.raises(ValueError) as error:
        crear_indicador(nombre, parametros)
    assert fragmento in str(error.value)


@pytest.mark.parametrize(("nombre", "clase", "parametros"), [
    ("sma", Sma, {"periodo": 20}),
    ("ema", Ema, {"periodo": 20}),
    ("rsi", Rsi, {"periodo": 14}),
    ("macd", Macd, {"rapido": 12, "lento": 26, "senal": 9}),
    ("bollinger", BandasBollinger, {"periodo": 20, "desviaciones": 2.0}),
    ("volatilidad", Volatilidad, {"periodo": 20}),
])
def test_crea_cada_indicador_con_sus_valores_por_defecto(
    nombre: str, clase: type, parametros: dict[str, object]
) -> None:
    indicador = crear_indicador(nombre)
    assert isinstance(indicador, clase)
    assert indicador.parametros() == parametros


def test_usa_los_parametros_recibidos_e_ignora_los_ajenos() -> None:
    rsi = crear_indicador(" RSI ", {"periodo": "7", "intervalo": "1d"})
    assert rsi.nombre() == "rsi"
    assert rsi.parametros() == {"periodo": 7}
    macd = crear_indicador("macd", {"rapido": "5", "lento": "10", "senal": "3"})
    assert macd.parametros() == {"rapido": 5, "lento": 10, "senal": 3}
    assert crear_indicador("bollinger", {"desviaciones": "1.5"}).parametros() == {"periodo": 20, "desviaciones": 1.5}


def test_nombre_faltante_o_desconocido() -> None:
    assert_invalido("Falta el parámetro 'indicador'", None, {})
    assert_invalido("Falta el parámetro 'indicador'", " ", {})
    assert_invalido("Indicador desconocido: 'adx'", "adx", {})
    assert_invalido(NOMBRES, "adx", {})


def test_periodo_debe_ser_al_menos_dos_y_entero() -> None:
    assert_invalido("entre 2 y 1000", "sma", {"periodo": "1"})
    assert_invalido("entre 2 y 1000", "ema", {"periodo": "0"})
    assert_invalido("entre 2 y 1000", "rsi", {"periodo": "1001"})
    assert_invalido("'periodo' inválido: 'abc'", "volatilidad", {"periodo": "abc"})
    assert_invalido("'periodo' inválido", "sma", {"periodo": "3.5"})


def test_parametros_invalidos_del_macd_y_bollinger() -> None:
    assert_invalido("'lento' (12) debe ser mayor que 'rapido' (26)", "macd", {"rapido": "26", "lento": "12"})
    assert_invalido("'senal' inválido", "macd", {"senal": "1"})
    assert_invalido("'desviaciones' inválido", "bollinger", {"desviaciones": "0"})
    assert_invalido("'desviaciones' inválido", "bollinger", {"desviaciones": "x"})


def test_periodo_mayor_que_las_velas_da_serie_vacia_no_error() -> None:
    assert crear_indicador("sma", {"periodo": "500"}).calcular(lineales(10, 1, 1)).esta_vacia()
    assert crear_indicador("macd").calcular_series(lineales(10, 1, 1))["senal"].esta_vacia()
