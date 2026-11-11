"""La cuenta de demostración, con velas sintéticas y una base en memoria."""

import math
import time

import pytest

from bitcoinai.demo import CORREO, HORA_MS, VelaSimple, crear_demo, generar_contrasena
from bitcoinai.persistencia import AlmacenBaseDatos
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.simulacion import Cartera, EstadoOrden
from bitcoinai.simulacion.estadisticas import calcular
from tests.usuarios.entorno import CLIENTE, crear_entorno


def velas_sinteticas(n: int = 1000) -> tuple[VelaSimple, ...]:
    ahora = int(time.time() * 1000) // HORA_MS * HORA_MS
    return tuple(VelaSimple(ahora - (n - i) * HORA_MS, p, p * 1.004, p * 0.996)
                 for i in range(n) for p in (95_000 + 4_000 * math.sin(i / 37) + 1_500 * math.sin(i / 5),))


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
