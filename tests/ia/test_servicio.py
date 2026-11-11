import time

import pytest

from bitcoinai.ia.servicio import DatosInsuficientesError, ServicioIA
from bitcoinai.modelo import Intervalo
from tests.apoyo.fuente_falsa import FuenteFalsa, generar_velas


class Reloj:
    def __init__(self) -> None:
        self.ahora = time.time() + 10 * 365 * 86400  # todas las velas falsas ya cerraron

    def __call__(self) -> float:
        return self.ahora


def test_entrena_mide_y_predice() -> None:
    servicio = ServicioIA(FuenteFalsa(), "BTCUSDT", reloj=Reloj())
    p = servicio.predecir(Intervalo.D1)
    # 500 velas falsas: 449 muestras (50 de calentamiento y la última sin etiqueta).
    assert (p.muestras_entrenamiento, p.muestras_prueba) == (359, 90)
    assert tuple(m.nombre for m in p.modelos) == ("Regresión logística", "Árbol de decisión", "k vecinos")
    assert sum(m.peso or 0 for m in p.modelos) == pytest.approx(1.0)
    assert 0 <= p.comite.probabilidad <= 1 and p.comite.direccion in ("SUBE", "BAJA")
    assert p.prueba.tamanio() == 90
    # Cada punto de prueba trae cuánto cambió el precio en la vela siguiente, coherente con "subio".
    assert all((q.rendimiento > 0) == q.subio for q in p.prueba if q.rendimiento != 0)
    assert all(m.metricas.muestras == 90 for m in p.modelos)
    assert "No es asesoría financiera" in p.aviso


def test_usa_la_cache_hasta_que_vence() -> None:
    fuente, reloj = FuenteFalsa(), Reloj()
    servicio = ServicioIA(fuente, "BTCUSDT", duracion_cache_s=600, reloj=reloj)
    primera = servicio.predecir(Intervalo.D1)
    assert servicio.predecir(Intervalo.D1) is primera
    assert fuente.llamadas_velas == 1
    reloj.ahora += 601
    assert servicio.predecir(Intervalo.D1) is not primera
    assert fuente.llamadas_velas == 2


def test_pocas_velas() -> None:
    servicio = ServicioIA(FuenteFalsa(generar_velas(150, Intervalo.D1)), "BTCUSDT", reloj=Reloj())
    with pytest.raises(DatosInsuficientesError, match="al menos 200"):
        servicio.predecir(Intervalo.D1)
