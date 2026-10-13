import pytest

from bitcoinai.ia.caracteristicas import CALENTAMIENTO, NOMBRES, construir_muestras
from bitcoinai.modelo import Vela


def velas(cierres: list[float]) -> list[Vela]:
    return [Vela(i * 1000, c, c * 1.01, c * 0.99, c, 10.0 + i % 3, i * 1000 + 999) for i, c in enumerate(cierres)]


def test_una_muestra_por_vela_despues_del_calentamiento_menos_la_ultima() -> None:
    muestras, ultima, tiempo = construir_muestras(velas([100 + i for i in range(80)]))
    assert muestras.tamanio() == 80 - CALENTAMIENTO - 1
    assert ultima is not None and len(ultima) == len(NOMBRES)
    assert tiempo == 79_000
    assert muestras.obtener(0).tiempo == CALENTAMIENTO * 1000


def test_la_etiqueta_dice_si_la_siguiente_subio() -> None:
    cierres = [100.0] * 60
    cierres[51] = 101  # después de la vela 50 sube
    cierres[52] = 99  # después de la 51 baja
    muestras, _, _ = construir_muestras(velas(cierres))
    assert (muestras.obtener(0).etiqueta, muestras.obtener(1).etiqueta) == (1, 0)


def test_caracteristicas_de_una_subida_constante() -> None:
    muestras, ultima, _ = construir_muestras(velas([100 * 1.01**i for i in range(70)]))
    assert ultima is not None
    rinde1, rinde5, _, rsi, *_ = ultima
    assert rinde1 == pytest.approx(0.01)
    assert rinde5 == pytest.approx(1.01**5 - 1)
    assert rsi == pytest.approx(100.0)  # nunca bajó
    assert ultima[5] == pytest.approx(0.0, abs=1e-12)  # volatilidad cero: siempre el mismo rendimiento
    assert all(m.etiqueta == 1 for m in muestras)


def test_no_mira_el_futuro() -> None:
    base = [100 + (i % 7) for i in range(70)]
    distinto_al_final = base[:-1] + [500.0]
    a, _, _ = construir_muestras(velas(base))
    b, _, _ = construir_muestras(velas(distinto_al_final))
    # Cambiar la última vela solo cambia la etiqueta de la muestra anterior, no sus características.
    assert a.obtener(a.tamanio() - 1).caracteristicas == b.obtener(b.tamanio() - 1).caracteristicas


def test_sin_velas_suficientes() -> None:
    muestras, ultima, tiempo = construir_muestras(velas([100.0] * 10))
    assert muestras.esta_vacia() and ultima is None and tiempo is None
