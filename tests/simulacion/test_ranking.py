import random

from bitcoinai.estructuras import Lista
from bitcoinai.simulacion.ranking import Clasificado, Participante, alias_publico, mejores, posicion_de


def p(usuario_id: int, rentabilidad: float) -> Participante:
    return Participante(usuario_id, 10_000 * (1 + rentabilidad), rentabilidad)


def ids(clasificados: Lista[Clasificado]) -> tuple[int, ...]:
    return tuple(c.participante.usuario_id for c in clasificados)


def test_los_k_mejores_del_primero_al_ultimo() -> None:
    gente = (p(1, 0.01), p(2, -0.05), p(3, 0.20), p(4, 0.07), p(5, 0.15))
    top = mejores(gente, 3)
    assert ids(top) == (3, 5, 4)
    assert tuple(c.posicion for c in top) == (1, 2, 3)


def test_con_empate_gana_el_que_se_registro_antes() -> None:
    assert ids(mejores((p(9, 0.1), p(2, 0.1), p(5, 0.1)), 2)) == (2, 5)


def test_menos_participantes_que_k_y_k_cero() -> None:
    assert ids(mejores((p(1, 0.0),), 10)) == (1,)
    assert ids(mejores((p(1, 0.0),), 0)) == ()
    assert ids(mejores((), 5)) == ()


def test_coincide_con_ordenar_a_todos() -> None:
    azar = random.Random(2)
    gente = tuple(p(i, round(azar.uniform(-0.3, 0.3), 2)) for i in range(1, 400))
    esperado = tuple(x.usuario_id for x in sorted(gente, key=lambda x: (-x.rentabilidad, x.usuario_id))[:10])
    assert ids(mejores(gente, 10)) == esperado


def test_posicion_de_un_usuario() -> None:
    gente = (p(1, 0.01), p(2, 0.30), p(3, 0.01), p(4, -0.1))
    puesto = posicion_de(gente, 3)
    assert puesto is not None and puesto.posicion == 3  # le ganan 2 y 1 (empate, se registró antes)
    assert posicion_de(gente, 99) is None


def test_alias_estable_y_sin_datos_personales() -> None:
    assert alias_publico(7) == alias_publico(7)
    assert alias_publico(7) != alias_publico(8)
    animal, gema, numero = alias_publico(7).split(" ")
    assert animal and gema and len(numero) == 2
