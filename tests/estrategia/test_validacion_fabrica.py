import pytest

from bitcoinai.estrategia import (
    Backtester,
    CruceDeMedias,
    EstrategiaCombinada,
    EstrategiaMacd,
    EstrategiaRsi,
    Senal,
    ValidacionEntrenamientoPrueba,
    candidatos,
    crear_estrategia,
)
from bitcoinai.modelo import Intervalo
from tests.apoyo.fuente_falsa import INICIO, generar_velas
from tests.estrategia.sinteticas import DIA, EstrategiaGuion, alcista_tras_caida, lateral_plano

# ---------- validación entrenamiento / prueba ----------


def test_division_setenta_treinta_no_mezcla_datos() -> None:
    velas = generar_velas(100, Intervalo.D1)  # siempre sube
    ultima_de_entrenamiento = INICIO + 69 * DIA
    quieto = EstrategiaGuion("quieto", Senal.MANTENER)
    comprador = EstrategiaGuion("comprador", Senal.COMPRAR)

    r = ValidacionEntrenamientoPrueba(Backtester(), 0.7).ejecutar((quieto, comprador), velas)

    assert (r.velas_entrenamiento, r.velas_prueba) == (70, 30)
    # El descartado solo vio velas de entrenamiento.
    assert all(t <= ultima_de_entrenamiento for t in quieto.tiempos_vistos)
    # El elegido: sus primeras 70 llamadas (entrenamiento) tampoco vieron velas de prueba.
    assert all(t <= ultima_de_entrenamiento for i, t in enumerate(comprador.tiempos_vistos) if i < 70)
    # Los dos tramos no se solapan.
    assert r.entrenamiento.tiempo_fin < r.prueba.tiempo_inicio
    assert r.prueba.tiempo_inicio == INICIO + 70 * DIA
    assert (r.entrenamiento.velas_analizadas, r.prueba.velas_analizadas) == (70, 30)


def test_elige_el_mejor_candidato_segun_el_entrenamiento_y_lo_mide_en_prueba() -> None:
    velas = generar_velas(100, Intervalo.D1)
    r = ValidacionEntrenamientoPrueba(Backtester(), 0.7).ejecutar(
        (EstrategiaGuion("quieto", Senal.MANTENER), EstrategiaGuion("comprador", Senal.COMPRAR)), velas)
    assert r.estrategia == "comprador"
    assert r.parametros_elegidos == {"nombre": "comprador"}
    assert r.candidatos.tamanio() == 2
    assert r.candidatos.primero().rentabilidad == 0
    assert r.candidatos.ultimo().rentabilidad > 0
    assert r.prueba.rentabilidad_total > 0
    assert r.prueba.numero_operaciones == 1


def test_en_prueba_las_velas_de_entrenamiento_solo_sirven_de_historial() -> None:
    unico = EstrategiaGuion("unico", Senal.MANTENER)
    ValidacionEntrenamientoPrueba(Backtester(), 0.7).ejecutar((unico,), generar_velas(10, Intervalo.D1))
    # 7 llamadas de entrenamiento (tamaños 1..7) y 3 de prueba (tamaños 8..10)
    assert tuple(unico.tamanios_vistos) == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)


def test_validacion_con_estrategia_real_devuelve_todos_los_candidatos() -> None:
    r = ValidacionEntrenamientoPrueba(Backtester(), 0.7).ejecutar(candidatos("cruce"), alcista_tras_caida())
    assert r.candidatos.tamanio() == 9
    assert (r.velas_entrenamiento, r.velas_prueba) == (84, 36)


def test_validacion_parametros_invalidos() -> None:
    for fraccion in (1, 0):
        with pytest.raises(ValueError):
            ValidacionEntrenamientoPrueba(Backtester(), fraccion)
    with pytest.raises(ValueError):
        ValidacionEntrenamientoPrueba(Backtester(), 0.7).ejecutar((), lateral_plano())


# ---------- fábrica ----------


def test_fabrica_crea_cada_estrategia_con_sus_valores_por_defecto() -> None:
    cruce = crear_estrategia("cruce")
    assert isinstance(cruce, CruceDeMedias) and cruce.parametros() == {"corta": 20, "larga": 50}
    rsi = crear_estrategia("RSI")
    assert isinstance(rsi, EstrategiaRsi)
    assert rsi.parametros() == {"periodo": 14, "sobreventa": 30.0, "sobrecompra": 70.0}
    macd = crear_estrategia("macd")
    assert isinstance(macd, EstrategiaMacd) and macd.parametros() == {"rapido": 12, "lento": 26, "senal": 9}
    assert isinstance(crear_estrategia("combinada"), EstrategiaCombinada)


def test_fabrica_usa_los_parametros_recibidos() -> None:
    assert crear_estrategia("cruce", {"corta": "10", "larga": "30"}).parametros() == {"corta": 10, "larga": 30}
    combinada = crear_estrategia("combinada", {"pesoRsi": "0", "corta": "5", "larga": "15"})
    assert combinada.parametros()["pesos"] == {"cruce": 1.0, "rsi": 0.0, "macd": 1.0}
    estrategias = combinada.parametros()["estrategias"]
    assert isinstance(estrategias, dict) and estrategias["cruce"] == {"corta": 5, "larga": 15}


def test_fabrica_rechaza_nombres_y_parametros_invalidos() -> None:
    for nombre, parametros in (("magia", {}), (None, {}), ("rsi", {"sobreventa": "60"}), ("macd", {"senal": "x"})):
        with pytest.raises(ValueError):
            crear_estrategia(nombre, parametros)
    with pytest.raises(ValueError, match=r"^Parámetro 'larga' \(20\) debe ser mayor que 'corta' \(50\)$"):
        crear_estrategia("cruce", {"corta": "50", "larga": "20"})
    with pytest.raises(ValueError, match="mayor que 0"):
        crear_estrategia("combinada", {"pesoCruce": "0", "pesoRsi": "0", "pesoMacd": "0"})


def test_candidatos_de_cada_estrategia() -> None:
    assert (candidatos("cruce").tamanio(), candidatos("rsi").tamanio(), candidatos("macd").tamanio(),
            candidatos("combinada").tamanio()) == (9, 9, 3, 4)
    with pytest.raises(ValueError):
        candidatos("magia")
