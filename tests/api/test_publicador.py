"""Pruebas unitarias del Publicador y del Suscriptor (sin servidor HTTP)."""

import asyncio
import json
from collections.abc import Iterator

import pytest

from bitcoinai.api import ApiError
from bitcoinai.api.publicador import INICIO, LATIDO, Publicador, PublicadorDeUsuario, Suscriptor
from bitcoinai.mercado import MercadoError
from bitcoinai.simulacion import EstadoOrden, Orden, TipoOrden
from tests.apoyo.fuente_falsa import FuenteFalsa


@pytest.fixture
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    bucle = asyncio.new_event_loop()
    yield bucle
    bucle.close()


def leer_todo(loop: asyncio.AbstractEventLoop, suscriptor: Suscriptor) -> tuple[str, ...]:
    async def leer() -> tuple[str, ...]:
        mensajes: tuple[str, ...] = ()
        while (mensaje := await suscriptor.siguiente(0.01)) is not None:
            mensajes += (mensaje,)
        return mensajes
    return loop.run_until_complete(leer())


def test_publica_con_formato_sse_a_todos(loop: asyncio.AbstractEventLoop) -> None:
    publicador = Publicador(FuenteFalsa(), "BTCUSDT")
    a, b = publicador.suscribir(loop), publicador.suscribir(loop)
    orden = Orden(1, TipoOrden.COMPRA, 500.0, False, EstadoOrden.PENDIENTE, 10)
    publicador.publicar("orden", orden)
    publicador.publicar("otro", {"texto": "ñandú"})
    for suscriptor in (a, b):
        primero, segundo = leer_todo(loop, suscriptor)
        assert primero.startswith("event: orden\ndata: {") and primero.endswith("}\n\n")
        datos = json.loads(primero.split("data: ", 1)[1])
        assert (datos["id"], datos["estado"], datos["creadaEn"]) == (1, "PENDIENTE", 10)
        assert segundo == 'event: otro\ndata: {"texto":"ñandú"}\n\n'


def test_limite_de_conexiones_da_503(loop: asyncio.AbstractEventLoop) -> None:
    publicador = Publicador(FuenteFalsa(), "BTCUSDT", maximo=2)
    primero = publicador.suscribir(loop)
    publicador.suscribir(loop)
    with pytest.raises(ApiError) as error:
        publicador.suscribir(loop)
    assert error.value.codigo == 503
    assert error.value.mensaje == "Demasiadas conexiones de tiempo real abiertas (máximo 2); intenta más tarde"
    assert publicador.desuscribir(primero)
    assert not publicador.desuscribir(primero)  # dos veces es seguro
    assert primero.cerrado
    publicador.suscribir(loop)  # vuelve a haber lugar
    assert publicador.cantidad_suscriptores() == 2


def test_quita_del_medio_sin_afectar_a_los_demas(loop: asyncio.AbstractEventLoop) -> None:
    publicador = Publicador(FuenteFalsa(), "BTCUSDT")
    a, b, c = (publicador.suscribir(loop) for _ in range(3))
    publicador.desuscribir(b)
    publicador.publicar("x", 1)
    assert leer_todo(loop, a) == leer_todo(loop, c) == ("event: x\ndata: 1\n\n",)
    assert leer_todo(loop, b) == ()


def test_un_cliente_que_no_lee_se_quita(loop: asyncio.AbstractEventLoop) -> None:
    publicador = Publicador(FuenteFalsa(), "BTCUSDT")
    lento = publicador.suscribir(loop)
    lento._limite = 3
    for numero in range(4):
        publicador.publicar("x", numero)
    assert publicador.cantidad_suscriptores() == 0
    assert lento.cerrado


def test_precio_solo_con_suscriptores_y_sin_fallar(loop: asyncio.AbstractEventLoop) -> None:
    fuente = FuenteFalsa(precio=123.5)
    publicador = Publicador(fuente, "BTCUSDT")
    publicador.publicar_precio()
    assert fuente.llamadas_precio == 0  # nadie escucha: no se consulta
    suscriptor = publicador.suscribir(loop)
    publicador.publicar_precio()
    fuente.error = MercadoError("caída")
    publicador.publicar_precio()  # se salta, sin excepción
    (mensaje,) = leer_todo(loop, suscriptor)
    datos = json.loads(mensaje.removeprefix("event: precio\ndata: "))
    assert (datos["simbolo"], datos["precio"]) == ("BTCUSDT", 123.5)
    assert list(datos) == ["simbolo", "precio", "momento"]


def test_mensajes_saluda_reenvia_y_termina_al_cerrar(loop: asyncio.AbstractEventLoop) -> None:
    publicador = Publicador(FuenteFalsa(), "BTCUSDT")
    suscriptor = publicador.suscribir(loop)

    async def recorrer() -> tuple[str, ...]:
        recibidos: tuple[str, ...] = ()
        async for mensaje in publicador.mensajes(suscriptor):
            recibidos += (mensaje,)
            if len(recibidos) == 1:
                publicador.enviar_latido()
                publicador.publicar("x", 1)
            if len(recibidos) == 3:
                publicador.detener()
        return recibidos

    assert loop.run_until_complete(recorrer()) == (INICIO, LATIDO, "event: x\ndata: 1\n\n")
    assert publicador.cantidad_suscriptores() == 0


def test_el_hilo_publica_precio_y_latido_periodicamente(loop: asyncio.AbstractEventLoop) -> None:
    publicador = Publicador(FuenteFalsa(), "BTCUSDT", periodo_precio=0.01, periodo_latido=0.03)
    suscriptor = publicador.suscribir(loop)
    publicador.iniciar()
    publicador.iniciar()  # una segunda vez no hace nada

    async def esperar_ambos() -> set[str]:
        vistos: set[str] = set()
        while len(vistos) < 2:
            mensaje = await suscriptor.siguiente(5)
            assert mensaje is not None
            vistos.add("latido" if mensaje == LATIDO else mensaje.split("\n", 1)[0])
        return vistos

    try:
        vistos = loop.run_until_complete(esperar_ambos())
    finally:
        publicador.detener()
    assert vistos == {"event: precio", "latido"}


def test_maximo_invalido() -> None:
    with pytest.raises(ValueError):
        Publicador(FuenteFalsa(), "BTCUSDT", maximo=0)


def test_eventos_privados_solo_para_su_dueno(loop: asyncio.AbstractEventLoop) -> None:
    publicador = Publicador(FuenteFalsa(), "BTCUSDT")
    ana, ana_telefono = publicador.suscribir(loop, usuario_id=1), publicador.suscribir(loop, usuario_id=1)
    luis, anonimo = publicador.suscribir(loop, usuario_id=2), publicador.suscribir(loop)
    PublicadorDeUsuario(publicador, 1).publicar("cartera", {"btc": 1})
    publicador.publicar("precio", {"precio": 100})
    precio = 'event: precio\ndata: {"precio":100}\n\n'
    esperado_ana = ('event: cartera\ndata: {"btc":1}\n\n', precio)
    assert leer_todo(loop, ana) == leer_todo(loop, ana_telefono) == esperado_ana
    assert leer_todo(loop, luis) == leer_todo(loop, anonimo) == (precio,)
