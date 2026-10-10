import pytest

from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import MIGRACIONES, Migracion, migrar, version_actual


def tablas(bd: BaseDatos) -> set[str]:
    return {f["name"] for f in bd.todas("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_crea_todas_las_tablas_una_sola_vez() -> None:
    bd = BaseDatos(":memory:")
    assert version_actual(bd) == 0
    assert migrar(bd) == len(MIGRACIONES)
    assert {"usuarios", "codigos_respaldo", "sesiones", "desafios", "actividad", "simulaciones", "ordenes",
            "ordenes_creadas", "eventos_simulacion"} <= tablas(bd)
    assert version_actual(bd) == MIGRACIONES[-1].version
    assert migrar(bd) == 0  # la segunda vez no hay nada pendiente


def test_aplica_solo_las_que_faltan() -> None:
    bd = BaseDatos(":memory:")
    primera = Migracion(1, "a", ("CREATE TABLE a (x INTEGER)",))
    segunda = Migracion(2, "b", ("CREATE TABLE b (x INTEGER)",))
    assert migrar(bd, (primera,)) == 1
    assert migrar(bd, (primera, segunda)) == 1
    assert {"a", "b"} <= tablas(bd)
    assert version_actual(bd) == 2


def test_una_migracion_que_falla_no_deja_nada_a_medias() -> None:
    bd = BaseDatos(":memory:")
    rota = Migracion(1, "rota", ("CREATE TABLE a (x INTEGER)", "ESTO NO ES SQL"))
    with pytest.raises(Exception, match="syntax"):
        migrar(bd, (rota,))
    assert "a" not in tablas(bd)
    assert version_actual(bd) == 0


def test_base_mas_nueva_que_el_codigo() -> None:
    bd = BaseDatos(":memory:")
    bd.ejecutar("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="versión 99"):
        migrar(bd)


def test_tipo_de_documento_restringido() -> None:
    import sqlite3

    bd = BaseDatos(":memory:")
    migrar(bd)
    with pytest.raises(sqlite3.IntegrityError):
        bd.ejecutar(
            "INSERT INTO usuarios (nombre, apellido, correo_indice, correo_cifrado, tipo_documento, documento_indice,"
            " documento_cifrado, telefono_cifrado, contrasena_hash, creado_en, actualizado_en)"
            " VALUES ('a', 'b', x'01', x'01', 'PASAPORTE', x'02', x'02', x'03', 'h', 0, 0)")
