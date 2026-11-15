"""Los casos difíciles del almacén en archivos: archivos ocupados y datos dañados.

En Windows (antivirus, OneDrive) un archivo puede estar bloqueado un instante justo cuando
se lo quiere reemplazar; el almacén reintenta y, si no puede, falla de forma visible. Y
cuando un archivo dañado tampoco se puede apartar, la advertencia no puede tumbar la carga.
"""

import json
import os
from pathlib import Path

import pytest

from bitcoinai.persistencia import CARTERA, ORDENES, AlmacenArchivos
from tests.persistencia.test_almacen import estado_de_ejemplo


def test_reintenta_cuando_el_archivo_esta_ocupado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = os.replace
    bloqueos = {"restantes": 2}

    def replace_que_se_bloquea(origen: str | os.PathLike[str], destino: str | os.PathLike[str]) -> None:
        if bloqueos["restantes"] > 0:
            bloqueos["restantes"] -= 1
            raise PermissionError("otro programa tiene el archivo abierto")
        real(origen, destino)

    monkeypatch.setattr(os, "replace", replace_que_se_bloquea)
    almacen = AlmacenArchivos(tmp_path)
    almacen.guardar(estado_de_ejemplo())

    assert bloqueos["restantes"] == 0  # se agotaron los reintentos con éxito
    assert (tmp_path / CARTERA).exists()
    assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())


def test_si_el_archivo_sigue_ocupado_el_error_se_propaga(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "replace",
                        lambda *_: (_ for _ in ()).throw(PermissionError("siempre ocupado")))
    with pytest.raises(PermissionError):
        AlmacenArchivos(tmp_path).guardar(estado_de_ejemplo())


def test_la_cola_de_creadas_con_un_id_invalido_es_un_dano(tmp_path: Path) -> None:
    almacen = AlmacenArchivos(tmp_path)
    almacen.guardar(estado_de_ejemplo())
    datos = json.loads((tmp_path / ORDENES).read_text(encoding="utf-8"))
    datos["creadas"] = [1, 0, 3]
    (tmp_path / ORDENES).write_text(json.dumps(datos), encoding="utf-8")

    cargado = almacen.cargar()
    assert cargado is not None and cargado.cartera is None


def test_si_el_archivo_danado_no_se_puede_apartar_se_sigue_adelante(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    almacen = AlmacenArchivos(tmp_path)
    almacen.guardar(estado_de_ejemplo())
    (tmp_path / CARTERA).write_text("esto no es json", encoding="utf-8")

    def no_se_puede_mover(*_: object) -> None:
        raise OSError("permiso denegado")

    monkeypatch.setattr(os, "replace", no_se_puede_mover)
    cargado = almacen.cargar()

    assert cargado is not None
    assert cargado.cartera is None  # se empieza limpio, sin reventar
    assert (tmp_path / CARTERA).exists()  # quedó donde estaba, no se perdió
