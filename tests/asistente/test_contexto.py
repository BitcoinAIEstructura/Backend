"""El contexto de práctica que se le pasa a Claude en cada mensaje del chat.

Se prueban las ramas que no aparecían en ninguna prueba: cartera sin valorar, bot con
decisión y con error, la lista de órdenes ejecutadas (y su recorte a las cinco más
recientes) y el consejo del piloto. El texto es el contrato con el modelo, así que se
verifica el contenido exacto de cada línea.
"""

from bitcoinai.asistente import DatosUsuario
from bitcoinai.asistente.contexto import ORDENES_RECIENTES, armar_contexto
from bitcoinai.asistente.asistente import decimal, usdt
from bitcoinai.estrategia import Decision, Senal
from bitcoinai.estructuras import Lista
from bitcoinai.simulacion import ConsejoPiloto, ConfiguracionBot, EstadoBot, EstadoOrden, Orden, TipoOrden
from tests.asistente.test_asistente import bot, cartera, datos


def orden(id_orden: int, estado: EstadoOrden = EstadoOrden.EJECUTADA, **cambios: object) -> Orden:
    base: dict[str, object] = {
        "id": id_orden, "tipo": TipoOrden.COMPRA, "monto": 500.0, "todo": False, "estado": estado,
        "creada_en": id_orden * 1_000, "ejecutada_en": id_orden * 1_000 + 1, "precio_ejecucion": 60_000.0,
        "cantidad_btc": 0.00833333, "comision": 0.5, "motivo": "manual", "detalle": None,
    }
    base.update(cambios)
    return Orden(**base)  # type: ignore[arg-type]


def lista_de(*ordenes: Orden) -> Lista[Orden]:
    lista: Lista[Orden] = Lista()
    for o in ordenes:
        lista.agregar(o)
    return lista


def test_sin_cartera_lo_dice_y_no_inventa_cifras() -> None:
    texto = armar_contexto(DatosUsuario(cartera=None, bot=bot(), pendientes=0), lista_de(), None)
    assert "Cartera: no se pudo valorar ahora (el precio del mercado no respondió)." in texto
    assert "Precio de BTC ahora" not in texto


def test_cartera_con_ganancia() -> None:
    texto = armar_contexto(datos(cartera=cartera(ganancia=250.0)), lista_de(), None)
    assert f"Precio de BTC ahora: {usdt(60_000.5)} USDT." in texto
    assert "empezó con 10.000,00" in texto
    assert "(2,50 %)" in texto  # 250 sobre 10.000


def test_bot_apagado_en_modo_reglas() -> None:
    texto = armar_contexto(datos(bot=bot(activo=False)), lista_de(), None)
    assert "Bot: apagado, modo reglas (cruce de medias, RSI y MACD)" in texto
    assert "revisó el mercado 0 veces" in texto


def test_bot_encendido_en_modo_ia_con_decision_y_error() -> None:
    estado = bot(
        activo=True,
        configuracion=ConfiguracionBot(modo="ia", intervalo="4h", riesgo=0.15, stop_loss=0.03, take_profit=0.09),
        ciclos=7,
        ultima_decision=Decision(1, Senal.COMPRAR, 60_000.0, 0.72, "cruce alcista"),
        ultimo_error="Binance no respondió",
    )
    texto = armar_contexto(datos(bot=estado), lista_de(), None)
    assert "Bot: encendido, modo piloto IA, velas de 4h" in texto
    assert "riesgo 15 %, stop-loss 3,0 %, take-profit 9,0 %" in texto
    assert "revisó el mercado 7 veces" in texto
    assert f"Última decisión del bot: COMPRAR (confianza {decimal(0.72)}): cruce alcista" in texto
    assert "Último error del bot: Binance no respondió" in texto


def test_sin_ordenes_ejecutadas() -> None:
    texto = armar_contexto(datos(pendientes=2), lista_de(orden(1, EstadoOrden.PENDIENTE)), None)
    assert "Órdenes pendientes en la cola: 2." in texto
    assert "Todavía no tiene órdenes ejecutadas." in texto


def test_solo_cuentan_las_ejecutadas_y_solo_las_ultimas() -> None:
    ordenes = lista_de(
        *[orden(i) for i in range(1, 8)],
        orden(99, EstadoOrden.CANCELADA),
    )
    texto = armar_contexto(datos(), ordenes, None)
    assert "Órdenes ejecutadas en total: 7. Las más recientes:" in texto
    incluidas = [f"#{i}" for i in range(1, 8) if f"- #{i} " in texto]
    assert len(incluidas) == ORDENES_RECIENTES
    assert "- #1 " not in texto and "- #2 " not in texto  # las dos más viejas se recortan
    assert "- #7 " in texto
    assert "#99" not in texto  # una cancelada no se cuenta


def test_linea_de_orden_ejecutada() -> None:
    texto = armar_contexto(datos(), lista_de(orden(4)), None)
    assert f"- #4 COMPRA de {decimal(0.00833333, 8)} BTC a {usdt(60_000.0)} (manual)" in texto


def test_consejo_del_piloto() -> None:
    consejo = ConsejoPiloto(senal="COMPRAR", probabilidad=0.63, confianza=0.26, exactitud=0.58, base=0.51,
                            riesgo=0.2, stop_loss=0.05, take_profit=0.1, volatilidad=0.01, intervalo="1h",
                            tiempo_vela=1, precio=60_000.0, motivo="sube")
    texto = armar_contexto(datos(), lista_de(), consejo)
    assert ("Consejo actual de la IA (velas de 1h): COMPRAR; probabilidad de que suba 63 %; "
            "en datos no vistos acertó 58 % (base 51 %).") in texto


def test_el_motivo_largo_se_recorta_a_ochenta_caracteres() -> None:
    largo = "x" * 200
    texto = armar_contexto(datos(), lista_de(orden(1, motivo=largo)), None)
    assert f"({largo[:80]})" in texto and largo not in texto
