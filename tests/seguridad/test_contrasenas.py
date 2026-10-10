from bitcoinai.seguridad.contrasenas import PARAMETROS_RAPIDOS_PARA_PRUEBAS, HashContrasenas, ParametrosArgon2

HASHER = HashContrasenas(PARAMETROS_RAPIDOS_PARA_PRUEBAS)


def test_el_hash_es_argon2id_y_no_contiene_la_contrasena() -> None:
    h = HASHER.calcular("Clave-Segura-2026")
    assert h.startswith("$argon2id$")
    assert "Clave-Segura-2026" not in h


def test_verifica_la_correcta_y_rechaza_las_demas() -> None:
    h = HASHER.calcular("Clave-Segura-2026")
    assert HASHER.verificar(h, "Clave-Segura-2026")
    assert not HASHER.verificar(h, "clave-segura-2026")
    assert not HASHER.verificar(h, "")
    assert not HASHER.verificar("esto no es un hash", "Clave-Segura-2026")


def test_misma_contrasena_da_hashes_distintos_por_la_sal() -> None:
    assert HASHER.calcular("igual") != HASHER.calcular("igual")


def test_senuelo_siempre_falso() -> None:
    assert HASHER.verificar_senuelo("contraseña-señuelo-que-nunca-coincide") is False


def test_hash_debil_necesita_actualizarse() -> None:
    debil = HASHER.calcular("x")
    fuerte = HashContrasenas(ParametrosArgon2(iteraciones=2, memoria_kib=16, paralelismo=1))
    assert fuerte.necesita_actualizarse(debil)
    assert not HASHER.necesita_actualizarse(debil)
    assert HASHER.necesita_actualizarse("basura")


def test_parametros_por_defecto_son_los_de_owasp() -> None:
    p = ParametrosArgon2()
    assert (p.iteraciones, p.memoria_kib, p.paralelismo) == (3, 65536, 4)
