"""La cuenta de demostración, con velas sintéticas y una base en memoria."""

import math
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import bitcoinai.demo as modulo_demo
from bitcoinai.api import Configuracion
from bitcoinai.basedatos import BaseDatos
from bitcoinai.demo import (
    CORREO,
    HORA_MS,
    SEMILLA,
    VELAS,
    VelaSimple,
    construir_historia,
    crear_demo,
    generar_contrasena,
    guardar_credenciales,
    velas_reales,
)
from bitcoinai.persistencia import AlmacenBaseDatos
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.simulacion import Cartera, EstadoOrden, TipoEvento
from bitcoinai.simulacion.estadisticas import calcular
from bitcoinai.usuarios.modelo import DatosRegistro
from tests.usuarios.entorno import CLIENTE, crear_entorno


def velas_sinteticas(n: int = 1000) -> tuple[VelaSimple, ...]:
    ahora = int(time.time() * 1000) // HORA_MS * HORA_MS
    return tuple(VelaSimple(ahora - (n - i) * HORA_MS, p, p * 1.004, p * 0.996)
                 for i in range(n) for p in (95_000 + 4_000 * math.sin(i / 37) + 1_500 * math.sin(i / 5),))


def velas_con_caidas() -> tuple[VelaSimple, ...]:
    """Caminata aleatoria (semilla fija) con caídas fuertes: así aparece un stop-loss del bot."""
    azar = random.Random(1)
    ahora = int(time.time() * 1000) // HORA_MS * HORA_MS
    precio, velas = 90_000.0, []
    for i in range(VELAS):
        precio *= math.exp(azar.gauss(0, 0.012))
        velas.append(VelaSimple(ahora - (VELAS - i) * HORA_MS, precio, precio * 1.004, precio * 0.996))
    return tuple(velas)


def test_crea_la_cuenta_con_historial_coherente() -> None:
    entorno = crear_entorno()
    contrasena = generar_contrasena()
    uid = crear_demo(entorno.bd, Cifrador(bytes(32)), velas_sinteticas(), contrasena)
    # Se puede entrar con la contraseña generada (correo confirmado, sin dos pasos).
    entorno.reloj.ahora = time.time()
    resultado = entorno.servicio.iniciar_sesion(CORREO, contrasena, CLIENTE)
    assert resultado.usuario is not None and resultado.usuario.nombre == "Jonathan"

    estado = AlmacenBaseDatos(entorno.bd, uid).cargar()
    assert estado is not None and estado.cartera is not None
    ejecutadas = [o for o in estado.registro if o.estado is EstadoOrden.EJECUTADA]
    assert len(ejecutadas) >= 20
    assert any(o.estado is EstadoOrden.CANCELADA for o in estado.registro)
    assert any(o.estado is EstadoOrden.RECHAZADA for o in estado.registro)
    assert any(o.motivo.startswith("piloto IA") for o in ejecutadas)
    assert any(o.motivo.startswith("señal del bot") for o in ejecutadas)
    assert estado.cartera.btc > 0  # el piloto dejó una posición abierta
    # La cartera guardada es la que resulta de repetir las órdenes.
    cartera = Cartera(estado.cartera.saldo_inicial)
    for o in ejecutadas:
        if o.tipo.name == "COMPRA":
            cartera.comprar(o.monto or 0, o.precio_ejecucion or 0, 0.001)
        else:
            cartera.vender_todo(o.precio_ejecucion or 0, 0.001)
    assert cartera.saldo_usdt == pytest.approx(estado.cartera.saldo_usdt)
    # Eventos en orden cronológico y estadísticas con aciertos y fallos.
    momentos = [e.momento for e in estado.eventos]
    assert momentos == sorted(momentos)
    e = calcular(estado.registro, 10_000, 0.001, int(time.time() * 1000))
    assert e.ganadoras > 0 and e.perdedoras > 0
    assert entorno.bd.una("SELECT COUNT(*) AS n FROM alertas WHERE usuario_id = ?", (uid,))["n"] == 3  # type: ignore[index]

    # Volver a crearla reemplaza la anterior (no se duplica).
    crear_demo(entorno.bd, Cifrador(bytes(32)), velas_sinteticas(), generar_contrasena())
    assert entorno.bd.una("SELECT COUNT(*) AS n FROM usuarios")["n"] == 1  # type: ignore[index]


def test_la_historia_cubre_unos_cuarenta_dias() -> None:
    historia = construir_historia(velas_sinteticas(), random.Random(SEMILLA))
    ordenes = list(historia.registro)
    dias = (ordenes[-1].creada_en - ordenes[0].creada_en) / (24 * HORA_MS)
    assert 39 <= dias <= 43


def test_la_historia_es_reproducible_con_la_misma_semilla() -> None:
    velas = velas_sinteticas()
    una = construir_historia(velas, random.Random(SEMILLA))
    otra = construir_historia(velas, random.Random(SEMILLA))

    # Misma semilla, mismas órdenes y mismos eventos (los tiempos de ejecución no se comparan).
    assert [(o.id, o.tipo, o.estado, o.motivo, o.detalle) for o in una.registro] == \
           [(o.id, o.tipo, o.estado, o.motivo, o.detalle) for o in otra.registro]
    assert [(e.tipo, e.descripcion) for e in una.eventos] == \
           [(e.tipo, e.descripcion) for e in otra.eventos]


def test_velas_reales_lee_las_velas_de_binance(monkeypatch: pytest.MonkeyPatch) -> None:
    class ClienteFalso:
        def __init__(self, url: str) -> None:
            assert url == Configuracion().url_base_binance

        def obtener_velas(self, simbolo: str, intervalo: object, limite: int) -> list[object]:
            assert (simbolo, limite) == ("BTCUSDT", VELAS)
            return [SimpleNamespace(tiempo_apertura=1, cierre=2.0, maximo=3.0, minimo=1.0)]

    monkeypatch.setattr(modulo_demo, "ClienteBinance", ClienteFalso)
    assert velas_reales(Configuracion()) == (VelaSimple(1, 2.0, 3.0, 1.0),)


def test_sin_internet_usa_una_serie_sintetica(monkeypatch: pytest.MonkeyPatch,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    class SinRed:
        def __init__(self, url: str) -> None:
            pass

        def obtener_velas(self, *_: object) -> list[object]:
            raise OSError("sin red")

    monkeypatch.setattr(modulo_demo, "ClienteBinance", SinRed)
    velas = velas_reales(Configuracion())

    assert len(velas) == VELAS
    assert all(v.maximo >= v.cierre >= v.minimo > 0 for v in velas)
    assert [b.tiempo - a.tiempo for a, b in zip(velas, velas[1:], strict=False)] == [HORA_MS] * (VELAS - 1)
    assert "serie sintética" in capsys.readouterr().out


def test_generar_contrasena_reintenta_si_la_primera_no_cumple(monkeypatch: pytest.MonkeyPatch) -> None:
    intentos: list[str] = []
    real = DatosRegistro.validar

    def validar(*args: str) -> object:
        intentos.append(args[-1])
        if len(intentos) == 1:
            raise ValueError("no cumple la política")
        return real(*args)

    monkeypatch.setattr(DatosRegistro, "validar", staticmethod(validar))
    contrasena = generar_contrasena()

    assert len(intentos) == 2 and contrasena == intentos[-1]


def test_la_etapa_del_bot_registra_un_stop_loss() -> None:
    historia = construir_historia(velas_con_caidas(), random.Random(1))

    stops = [o for o in historia.registro
             if o.estado is EstadoOrden.EJECUTADA and o.motivo.startswith("stop-loss")]
    assert stops, "una caminata con caídas fuertes debería cortar una pérdida del bot"
    assert any(e.tipo is TipoEvento.STOP_LOSS and e.descripcion.startswith("El bot vende todo")
               for e in historia.eventos)


def test_guardar_credenciales_deja_un_archivo_para_la_persona(tmp_path: Path) -> None:
    archivo = tmp_path / "credenciales.md"
    contrasena = "NxAbCdEfGhIjKl#7"

    guardar_credenciales(archivo, contrasena)

    texto = archivo.read_text(encoding="utf-8")
    assert f"- Correo: `{CORREO}`" in texto
    assert f"- Contraseña: `{contrasena}`" in texto
    assert "Jonathan Mideros" in texto
    assert "no lo subas a GitHub" in texto
    assert "http://localhost:3000/iniciar-sesion" in texto


def test_main_crea_la_cuenta_y_guarda_la_contrasena(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    class SinRed:
        def __init__(self, url: str) -> None:
            pass

        def obtener_velas(self, *_: object) -> list[object]:
            raise OSError("sin internet")

    monkeypatch.chdir(tmp_path)  # sin .env del proyecto
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "datos"))
    monkeypatch.delenv("BASE_DATOS", raising=False)
    monkeypatch.setattr(sys, "argv", ["bitcoinai.demo", "--guardar-en", str(tmp_path / "credenciales.md")])
    monkeypatch.setattr(modulo_demo, "ClienteBinance", SinRed)

    modulo_demo.main()

    assert "Cuenta de demostración lista" in capsys.readouterr().out
    texto = (tmp_path / "credenciales.md").read_text(encoding="utf-8")
    assert CORREO in texto
    bd = BaseDatos(tmp_path / "datos" / "bitcoinai.db")
    assert bd.una("SELECT COUNT(*) AS n FROM usuarios")["n"] == 1  # type: ignore[index]
