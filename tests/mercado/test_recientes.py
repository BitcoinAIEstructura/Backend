from bitcoinai.mercado.recientes import PreciosRecientes


def test_guarda_en_orden_y_descarta_los_muy_seguidos() -> None:
    recientes = PreciosRecientes(capacidad=5)
    assert recientes.registrar(0, 100.0)
    assert not recientes.registrar(1500, 101.0)  # menos de 2 s después
    assert recientes.registrar(2000, 102.0)
    assert not recientes.registrar(1000, 99.0)  # más viejo que el último
    assert tuple(recientes.instantanea()) == ((0, 100.0), (2000, 102.0))


def test_al_llenarse_pisa_al_mas_viejo() -> None:
    recientes = PreciosRecientes(capacidad=3, separacion_minima_ms=0)
    for i in range(5):
        recientes.registrar(i, float(i))
    assert tuple(p for _, p in recientes.instantanea()) == (2.0, 3.0, 4.0)
    frente, tamanio, casillas = recientes.estado_del_anillo()
    # Casillas en memoria: 3 pisó a 0 (casilla 0) y 4 pisó a 1 (casilla 1); el frente es la 2.
    assert (frente, tamanio, tuple(casillas)) == (2, 3, (3.0, 4.0, 2.0))
    assert recientes.capacidad() == 3


def test_anillo_vacio() -> None:
    frente, tamanio, casillas = PreciosRecientes(capacidad=2).estado_del_anillo()
    assert (frente, tamanio, tuple(casillas)) == (0, 0, (None, None))
