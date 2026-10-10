import threading
from pathlib import Path

import pytest

from bitcoinai.basedatos import BaseDatos


@pytest.fixture
def bd() -> BaseDatos:
    base = BaseDatos(":memory:")
    base.ejecutar("CREATE TABLE notas (id INTEGER PRIMARY KEY, texto TEXT NOT NULL)")
    return base


def test_insertar_y_leer(bd: BaseDatos) -> None:
    primero = bd.ejecutar("INSERT INTO notas (texto) VALUES (?)", ("hola",))
    segundo = bd.ejecutar("INSERT INTO notas (texto) VALUES (:texto)", {"texto": "chao"})
    assert (primero, segundo) == (1, 2)
    fila = bd.una("SELECT texto FROM notas WHERE id = ?", (2,))
    assert fila is not None and fila["texto"] == "chao"
    assert bd.una("SELECT texto FROM notas WHERE id = ?", (9,)) is None
    assert tuple(f["texto"] for f in bd.todas("SELECT texto FROM notas ORDER BY id")) == ("hola", "chao")


def test_los_parametros_evitan_la_inyeccion_de_sql(bd: BaseDatos) -> None:
    malicioso = "x'); DROP TABLE notas; --"
    bd.ejecutar("INSERT INTO notas (texto) VALUES (?)", (malicioso,))
    fila = bd.una("SELECT texto FROM notas")
    assert fila is not None and fila["texto"] == malicioso


def test_contar_cambios(bd: BaseDatos) -> None:
    for texto in ("a", "b", "c"):
        bd.ejecutar("INSERT INTO notas (texto) VALUES (?)", (texto,))
    assert bd.contar_cambios("DELETE FROM notas WHERE texto != ?", ("a",)) == 2


def test_transaccion_deshace_todo_si_falla(bd: BaseDatos) -> None:
    with pytest.raises(RuntimeError), bd.transaccion():
        bd.ejecutar("INSERT INTO notas (texto) VALUES (?)", ("a",))
        raise RuntimeError("falla a mitad")
    assert bd.una("SELECT COUNT(*) AS n FROM notas")["n"] == 0  # type: ignore[index]
    with bd.transaccion():
        bd.ejecutar("INSERT INTO notas (texto) VALUES (?)", ("b",))
    assert bd.una("SELECT COUNT(*) AS n FROM notas")["n"] == 1  # type: ignore[index]


def test_claves_foraneas_activadas(bd: BaseDatos) -> None:
    import sqlite3

    bd.ejecutar("CREATE TABLE hijos (id INTEGER PRIMARY KEY, nota INTEGER NOT NULL REFERENCES notas(id))")
    with pytest.raises(sqlite3.IntegrityError):
        bd.ejecutar("INSERT INTO hijos (nota) VALUES (?)", (99,))


def test_varios_hilos_a_la_vez(tmp_path: Path) -> None:
    bd = BaseDatos(tmp_path / "sub" / "app.db")
    bd.ejecutar("CREATE TABLE notas (id INTEGER PRIMARY KEY, texto TEXT NOT NULL)")

    def escribir(n: int) -> None:
        for i in range(50):
            bd.ejecutar("INSERT INTO notas (texto) VALUES (?)", (f"{n}-{i}",))

    hilos = tuple(threading.Thread(target=escribir, args=(n,)) for n in range(4))
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert bd.una("SELECT COUNT(*) AS n FROM notas")["n"] == 200  # type: ignore[index]
    bd.cerrar()
    assert (tmp_path / "sub" / "app.db").exists()
