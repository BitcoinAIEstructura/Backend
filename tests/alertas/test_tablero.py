from bitcoinai.alertas.tablero import Alerta, EstadoAlerta, TableroAlertas, TipoAlerta
from bitcoinai.estructuras import Lista


def alerta(id_: int, tipo: TipoAlerta, precio: float, usuario: int = 1) -> Alerta:
    return Alerta(id_, usuario, tipo, precio, EstadoAlerta.ACTIVA, 0)


def ids(alertas: Lista[Alerta]) -> tuple[int, ...]:
    return tuple(a.id for a in alertas)


def tablero(*alertas: Alerta) -> TableroAlertas:
    t = TableroAlertas()
    for a in alertas:
        t.agregar(a)
    return t


def test_solo_disparan_las_que_se_cumplen() -> None:
    t = tablero(alerta(1, TipoAlerta.SUBE_A, 85_000), alerta(2, TipoAlerta.SUBE_A, 90_000),
                alerta(3, TipoAlerta.BAJA_A, 80_000), alerta(4, TipoAlerta.BAJA_A, 75_000))
    assert ids(t.revisar(84_000, 1)) == ()
    assert ids(t.revisar(86_000, 2)) == (1,)
    assert ids(t.revisar(79_000, 3)) == (3,)
    assert t.tamanio() == 2
    assert t.proximas() == (90_000, 75_000)


def test_un_salto_grande_dispara_varias_en_orden() -> None:
    t = tablero(alerta(1, TipoAlerta.SUBE_A, 90_000), alerta(2, TipoAlerta.SUBE_A, 85_000),
                alerta(3, TipoAlerta.SUBE_A, 99_000))
    disparadas = t.revisar(95_000, 7)
    assert ids(disparadas) == (2, 1)  # de la más cercana a la más lejana
    primera = disparadas.obtener(0)
    assert (primera.estado, primera.disparada_en, primera.precio_disparo) == (EstadoAlerta.DISPARADA, 7, 95_000)


def test_llegar_justo_al_precio_cuenta() -> None:
    t = tablero(alerta(1, TipoAlerta.SUBE_A, 85_000), alerta(2, TipoAlerta.BAJA_A, 80_000))
    assert ids(t.revisar(85_000, 1)) == (1,)
    assert ids(t.revisar(80_000, 2)) == (2,)


def test_cancelar_es_perezoso_pero_nunca_dispara() -> None:
    t = tablero(alerta(1, TipoAlerta.SUBE_A, 85_000), alerta(2, TipoAlerta.SUBE_A, 86_000))
    assert t.cancelar(1)
    assert not t.cancelar(1)
    assert t.tamanio() == 1
    assert ids(t.revisar(100_000, 1)) == (2,)
    assert t.proximas() == (None, None)


def test_cuenta_las_activas_de_cada_usuario() -> None:
    t = tablero(alerta(1, TipoAlerta.SUBE_A, 1, usuario=7), alerta(2, TipoAlerta.BAJA_A, 1, usuario=7),
                alerta(3, TipoAlerta.SUBE_A, 1, usuario=8))
    assert (t.activas_de(7), t.activas_de(8), t.activas_de(9)) == (2, 1, 0)
