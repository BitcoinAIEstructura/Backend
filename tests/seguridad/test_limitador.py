import pytest

from bitcoinai.seguridad.limitador import LimitadorIntentos


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


def test_bloquea_al_llegar_al_maximo_y_libera_al_pasar_la_ventana() -> None:
    reloj = Reloj()
    limitador = LimitadorIntentos(3, 60, reloj)
    for _ in range(2):
        limitador.registrar("ana")
        reloj.ahora += 10
    assert limitador.permitido("ana")
    limitador.registrar("ana")  # tercer intento, en t=1020
    assert not limitador.permitido("ana")
    assert limitador.espera("ana") == pytest.approx(40)  # el primero (t=1000) vence en t=1060
    reloj.ahora = 1060
    assert limitador.permitido("ana")


def test_las_claves_son_independientes() -> None:
    limitador = LimitadorIntentos(1, 60, Reloj())
    limitador.registrar("ana")
    assert not limitador.permitido("ana")
    assert limitador.permitido("luis")


def test_reiniciar_y_limpieza_automatica() -> None:
    reloj = Reloj()
    limitador = LimitadorIntentos(2, 60, reloj)
    limitador.registrar("ana")
    limitador.registrar("luis")
    limitador.reiniciar("ana")
    assert limitador.cantidad_claves() == 1
    reloj.ahora += 61
    assert limitador.permitido("luis")
    assert limitador.cantidad_claves() == 0  # las colas vacías no ocupan memoria


def test_nunca_guarda_mas_del_maximo() -> None:
    limitador = LimitadorIntentos(3, 60, Reloj())
    for _ in range(100):
        limitador.registrar("bot")
    assert limitador._intentos["bot"].tamanio() == 3


def test_parametros_invalidos() -> None:
    with pytest.raises(ValueError):
        LimitadorIntentos(0, 60)
    with pytest.raises(ValueError):
        LimitadorIntentos(5, 0)
