import pytest

from bitcoinai.estrategia import Backtester, CruceDeMedias, EstrategiaCombinada, Senal
from bitcoinai.estructuras import ListaDoble
from bitcoinai.modelo import Vela
from tests.estrategia.sinteticas import DIA, EstrategiaGuion, alcista_tras_caida, primeras, velas


def cinco_velas() -> ListaDoble[Vela]:
    """Aperturas 100, 110, 120, 130, 140 y cierres 5 más arriba."""
    return velas((100, 110, 120, 130, 140), (105, 115, 125, 135, 145))


# ---------- comisión y ejecución ----------


def test_comision_se_descuenta_en_la_compra_y_en_la_venta() -> None:
    # Señal de compra en la vela 0 → se compra en la apertura de la vela 1 (110).
    # Señal de venta en la vela 2 → se vende en la apertura de la vela 3 (130).
    guion = EstrategiaGuion().en(0, Senal.COMPRAR).en(2, Senal.VENDER)
    r = Backtester(1000, 0.001).ejecutar(guion, cinco_velas())

    comision_compra = 1000 * 0.001
    btc = (1000 - comision_compra) / 110
    bruto = btc * 130
    comision_venta = bruto * 0.001
    capital_final = bruto - comision_venta

    assert r.capital_final == pytest.approx(capital_final)
    assert r.comisiones_pagadas == pytest.approx(comision_compra + comision_venta)
    assert r.rentabilidad_total == pytest.approx(capital_final / 1000 - 1)
    assert r.numero_operaciones == 1
    op = r.operaciones.primero()
    assert (op.tiempo_entrada, op.precio_entrada, op.tiempo_salida, op.precio_salida) == (DIA, 110, 3 * DIA, 130)
    assert op.cantidad_btc == pytest.approx(btc)
    assert op.comisiones == pytest.approx(comision_compra + comision_venta)
    assert op.ganancia == pytest.approx(capital_final - 1000)
    assert op.rentabilidad == pytest.approx(op.ganancia / 1000)
    assert op.motivo_salida == "guion dice VENDER en la vela 2."


def test_sin_comision_la_ganancia_es_el_cambio_de_precio() -> None:
    r = Backtester(1000, 0).ejecutar(EstrategiaGuion().en(0, Senal.COMPRAR).en(2, Senal.VENDER), cinco_velas())
    assert r.capital_final == pytest.approx(1000 * 130 / 110)
    assert r.comisiones_pagadas == 0


def test_comprar_y_mantener_va_de_la_primera_apertura_al_ultimo_cierre_con_comisiones() -> None:
    r = Backtester(1000, 0.001).ejecutar(EstrategiaGuion(), cinco_velas())
    assert r.rentabilidad_comprar_y_mantener == pytest.approx(0.999 * 0.999 * 145 / 100 - 1)
    assert (r.capital_final, r.rentabilidad_total, r.numero_operaciones, r.tasa_ganadoras) == (1000, 0, 0, 0)
    assert r.factor_beneficio is None


def test_posicion_abierta_al_final_se_cierra_al_ultimo_cierre() -> None:
    r = Backtester(1000, 0).ejecutar(EstrategiaGuion().en(0, Senal.COMPRAR), cinco_velas())
    op = r.operaciones.primero()
    assert (op.precio_salida, op.tiempo_salida) == (145, 4 * DIA)
    assert op.motivo_salida == "Cierre forzado al final del periodo."
    assert r.capital_final == pytest.approx(1000 * 145 / 110)


def test_senal_en_la_ultima_vela_no_llega_a_ejecutarse() -> None:
    r = Backtester().ejecutar(EstrategiaGuion().en(4, Senal.COMPRAR), cinco_velas())
    assert (r.numero_operaciones, r.capital_final) == (0, 1000)


def test_solo_posiciones_largas() -> None:
    # VENDER sin posición se ignora; COMPRAR con posición también.
    guion = EstrategiaGuion().en(0, Senal.VENDER).en(1, Senal.COMPRAR).en(2, Senal.COMPRAR).en(3, Senal.VENDER)
    r = Backtester(1000, 0).ejecutar(guion, cinco_velas())
    assert r.numero_operaciones == 1
    assert (r.operaciones.primero().precio_entrada, r.operaciones.primero().precio_salida) == (120, 140)


# ---------- métricas ----------


def guion_ganadora_y_perdedora() -> tuple[EstrategiaGuion, ListaDoble[Vela]]:
    # op 1: compra a 100 (vela 1), vende a 120 (vela 3) → 1000 → 1200 (+200)
    # op 2: compra a 120 (vela 4), vende a 90 (vela 6)  → 1200 → 900  (−300)
    precios = (100.0, 100, 120, 120, 120, 90, 90)
    guion = EstrategiaGuion().en(0, Senal.COMPRAR).en(2, Senal.VENDER).en(3, Senal.COMPRAR).en(5, Senal.VENDER)
    return guion, velas(precios, precios)


def test_metricas_con_una_operacion_ganadora_y_una_perdedora() -> None:
    guion, datos = guion_ganadora_y_perdedora()
    r = Backtester(1000, 0).ejecutar(guion, datos)
    assert r.capital_final == pytest.approx(900)
    assert r.rentabilidad_total == pytest.approx(-0.1)
    assert (r.numero_operaciones, r.tasa_ganadoras) == (2, 0.5)
    assert r.factor_beneficio == pytest.approx(200 / 300)
    assert r.caida_maxima == pytest.approx(0.25)  # la curva baja de 1200 a 900
    assert (r.velas_analizadas, r.numero_decisiones, r.tiempo_inicio, r.tiempo_fin) == (7, 7, 0, 7 * DIA - 1)


def test_decisiones_recientes_salen_de_la_pila_de_la_mas_nueva_a_la_mas_vieja() -> None:
    guion, datos = guion_ganadora_y_perdedora()
    r = Backtester(1000, 0).ejecutar(guion, datos)
    orden = tuple(f"{d.senal.name}@{d.tiempo // DIA}" for d in r.decisiones_recientes)
    assert orden == ("VENDER@5", "COMPRAR@3", "VENDER@2", "COMPRAR@0")


def test_curva_de_capital_valora_la_posicion_al_cierre_de_cada_vela() -> None:
    r = Backtester(1000, 0).ejecutar(EstrategiaGuion().en(0, Senal.COMPRAR).en(2, Senal.VENDER), cinco_velas())
    btc = 1000 / 110
    esperado = (1000, btc * 115, btc * 125, btc * 130, btc * 130)
    assert tuple(p.tiempo for p in r.curva_capital) == tuple(i * DIA for i in range(5))
    assert tuple(p.valor for p in r.curva_capital) == pytest.approx(esperado)


# ---------- sin mirar el futuro ----------


def test_la_estrategia_solo_recibe_las_velas_hasta_la_actual() -> None:
    espia = EstrategiaGuion()
    Backtester().ejecutar(espia, alcista_tras_caida())
    assert tuple(espia.tamanios_vistos) == tuple(range(1, 121))
    assert tuple(espia.tiempos_vistos) == tuple(i * DIA for i in range(120))


def test_el_resultado_hasta_la_vela_t_no_cambia_al_agregar_velas_posteriores() -> None:
    todas = alcista_tras_caida()
    backtester = Backtester(1000, 0.001)
    corto = backtester.ejecutar(EstrategiaCombinada(), primeras(todas, 80))
    largo = backtester.ejecutar(EstrategiaCombinada(), todas)
    pares = tuple(zip(corto.curva_capital, largo.curva_capital, strict=False))
    assert len(pares) == 80
    for i, (p, q) in enumerate(pares):
        assert (p.tiempo, p.valor) == (q.tiempo, q.valor), f"la curva difiere en la vela {i}"
    assert corto.operaciones.primero().tiempo_entrada == largo.operaciones.primero().tiempo_entrada
    assert corto.operaciones.primero().precio_entrada == largo.operaciones.primero().precio_entrada


# ---------- periodo parcial y bordes ----------


def test_inicio_operaciones_usa_lo_anterior_solo_como_historial() -> None:
    espia = EstrategiaGuion()
    r = Backtester().ejecutar(espia, cinco_velas(), 2)
    assert tuple(espia.tamanios_vistos) == (3, 4, 5)  # ve las velas 0 y 1, pero solo decide en 2, 3 y 4
    assert (r.velas_analizadas, r.tiempo_inicio) == (3, 2 * DIA)
    assert r.rentabilidad_comprar_y_mantener == pytest.approx(0.999 * 0.999 * 145 / 120 - 1)


def test_sin_velas_no_hay_operaciones() -> None:
    r = Backtester(500, 0.001).ejecutar(CruceDeMedias(), ListaDoble())
    assert (r.capital_final, r.rentabilidad_comprar_y_mantener, r.velas_analizadas, r.caida_maxima) == (500, 0, 0, 0)


def test_parametros_invalidos() -> None:
    for crear in (lambda: Backtester(0, 0.001), lambda: Backtester(1000, -0.1), lambda: Backtester(1000, 1)):
        with pytest.raises(ValueError):
            crear()
    with pytest.raises(ValueError):
        Backtester().ejecutar(CruceDeMedias(), cinco_velas(), 6)
