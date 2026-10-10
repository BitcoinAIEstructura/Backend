import re

from bitcoinai.seguridad.respaldo import ALFABETO, generar_codigos, hash_codigo, normalizar_codigo


def test_diez_codigos_distintos_con_formato() -> None:
    codigos = tuple(generar_codigos())
    assert len(codigos) == 10 and len(set(codigos)) == 10
    assert all(re.fullmatch(rf"[{ALFABETO}]{{5}}-[{ALFABETO}]{{5}}", c) for c in codigos)


def test_se_aceptan_escritos_de_otra_forma() -> None:
    assert normalizar_codigo("abcde fghij") == normalizar_codigo("ABCDE-FGHIJ") == "ABCDEFGHIJ"
    assert hash_codigo("abcde-fghij") == hash_codigo("ABCDEFGHIJ")
    assert hash_codigo("ABCDE-FGHIJ") != hash_codigo("ABCDE-FGHIK")
