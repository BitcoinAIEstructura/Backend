"""Lo que la IA del chat puede proponer: una orden, encender o detener el bot, una alerta o
ir a una página.

Claude no ejecuta nada. Llama a una de estas herramientas, el servidor revisa que la propuesta
tenga sentido con los datos reales de la persona (¿le alcanza el saldo?, ¿tiene BTC para
vender?, ¿el bot ya está encendido?) y, si pasa, la devuelve como una ``Accion``: el frontend
la muestra como botón y solo al tocarlo se hace. La etiqueta del botón la escribe el servidor,
nunca la IA, para que diga exactamente lo que va a pasar.
"""

import math
from collections.abc import Mapping
from typing import Any

from bitcoinai.asistente.asistente import Accion, AlertaPropuesta, DatosUsuario, OrdenPropuesta, usdt

MONTO_MINIMO = 1.0
"""USDT: por debajo de esto la comisión se come la orden."""

PAGINAS: dict[str, tuple[str, str]] = {
    "panel": ("/panel", "Ir al Panel"),
    "mercado": ("/mercado", "Ver el Mercado"),
    "ordenes": ("/ordenes", "Ir a Órdenes"),
    "cartera": ("/cartera", "Ver mi Cartera"),
    "bot": ("/bot", "Ir al Bot"),
    "ia": ("/ia", "Ver Predicciones IA"),
    "liga": ("/liga", "Ver la Liga"),
    "como-funciona": ("/como-funciona", "Ver Cómo funciona"),
    "seguridad": ("/seguridad", "Ir a Seguridad"),
}


def _objeto(propiedades: Mapping[str, Any]) -> dict[str, Any]:
    """Esquema estricto: todas las propiedades obligatorias y ninguna extra."""
    return {"type": "object", "properties": dict(propiedades), "required": list(propiedades),
            "additionalProperties": False}


# Van en ``list`` y ``dict`` porque así las recibe el SDK de Anthropic (borde con un servicio externo).
HERRAMIENTAS: list[dict[str, Any]] = [
    {
        "name": "proponer_orden",
        "description": (
            "Propone a la persona una orden de práctica de compra o venta de BTC. Aparece como un botón que "
            "ella confirma; tú no la ejecutas. Úsala cuando la persona quiera invertir, pida una recomendación "
            "concreta o cuando el consejo de la IA y su cartera hagan razonable sugerir una operación. "
            "El monto es en USDT y debe caber en lo que tiene: en una compra, como máximo sus USDT "
            "disponibles; en una venta, como máximo el valor de su BTC (o vender_todo=true)."
        ),
        "strict": True,
        "input_schema": _objeto({
            "tipo": {"type": "string", "enum": ["COMPRA", "VENTA"]},
            "monto_usdt": {"type": ["number", "null"],
                           "description": "USDT a gastar (compra) o valor del BTC a vender; null si vender_todo."},
            "vender_todo": {"type": "boolean", "description": "Solo en VENTA: vender todo el BTC."},
        }),
    },
    {
        "name": "proponer_bot",
        "description": (
            "Propone encender o detener el bot de práctica. Aparece como un botón que la persona confirma. "
            "modo: 'ia' para el piloto IA, 'reglas' para la estrategia de cruce de medias, RSI y MACD, "
            "'actual' para dejar la configuración que ya tiene."
        ),
        "strict": True,
        "input_schema": _objeto({
            "accion": {"type": "string", "enum": ["ENCENDER", "DETENER"]},
            "modo": {"type": "string", "enum": ["ia", "reglas", "actual"]},
        }),
    },
    {
        "name": "proponer_alerta",
        "description": (
            "Propone una alerta de precio: avisa cuando BTC suba a (SUBE_A, por encima del precio actual) o "
            "baje a (BAJA_A, por debajo) un precio en USDT. Aparece como un botón que la persona confirma."
        ),
        "strict": True,
        "input_schema": _objeto({
            "tipo": {"type": "string", "enum": ["SUBE_A", "BAJA_A"]},
            "precio": {"type": "number"},
        }),
    },
    {
        "name": "proponer_pagina",
        "description": "Ofrece un botón para ir a una página de Nexabit donde la persona puede ver o hacer algo.",
        "strict": True,
        "input_schema": _objeto({"pagina": {"type": "string", "enum": list(PAGINAS)}}),
    },
]

NOMBRES = frozenset(h["name"] for h in HERRAMIENTAS)


def _numero(valor: object) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        return None
    return float(valor)


def validar(nombre: str, datos: Mapping[str, object], usuario: DatosUsuario,
            piloto_disponible: bool) -> Accion | None:
    """La ``Accion`` de una propuesta de la IA, o None si no tiene sentido con los datos reales.

    Complejidad: O(1).
    """
    if nombre == "proponer_orden":
        return _orden(datos, usuario)
    if nombre == "proponer_bot":
        return _bot(datos, usuario, piloto_disponible)
    if nombre == "proponer_alerta":
        return _alerta(datos, usuario)
    if nombre == "proponer_pagina":
        pagina = datos.get("pagina")
        if isinstance(pagina, str) and pagina in PAGINAS:
            ruta, etiqueta = PAGINAS[pagina]
            return Accion("IR", etiqueta, ruta)
    return None


def _orden(datos: Mapping[str, object], usuario: DatosUsuario) -> Accion | None:
    c = usuario.cartera
    tipo = datos.get("tipo")
    if c is None or tipo not in ("COMPRA", "VENTA"):
        return None  # sin precio no se puede revisar si alcanza
    if tipo == "VENTA" and datos.get("vender_todo") is True:
        if c.btc <= 0:
            return None
        return Accion("ORDEN", f"Vender todo mi BTC (≈ {usdt(c.valor_btc)} USDT)",
                      orden=OrdenPropuesta("VENTA", None, todo=True))
    monto = _numero(datos.get("monto_usdt"))
    if monto is None:
        return None
    monto = math.floor(monto * 100) / 100  # centavos, hacia abajo: nunca más de lo que hay
    tope = c.saldo_usdt if tipo == "COMPRA" else c.valor_btc
    if monto < MONTO_MINIMO or monto > tope:
        return None
    verbo = "Comprar" if tipo == "COMPRA" else "Vender"
    return Accion("ORDEN", f"{verbo} {usdt(monto)} USDT de BTC", orden=OrdenPropuesta(str(tipo), monto))


def _bot(datos: Mapping[str, object], usuario: DatosUsuario, piloto_disponible: bool) -> Accion | None:
    accion, modo = datos.get("accion"), datos.get("modo")
    if accion == "DETENER":
        return Accion("DETENER_BOT", "Sí, detén el bot") if usuario.bot.activo else None
    if accion != "ENCENDER" or usuario.bot.activo or modo not in ("ia", "reglas", "actual"):
        return None
    if modo == "ia":
        return Accion("INICIAR_BOT", "Encender el piloto IA", modo="ia") if piloto_disponible else None
    if modo == "reglas":
        return Accion("INICIAR_BOT", "Encender el bot con reglas", modo="reglas")
    return Accion("INICIAR_BOT", "Sí, enciende el bot")


def _alerta(datos: Mapping[str, object], usuario: DatosUsuario) -> Accion | None:
    tipo, precio = datos.get("tipo"), _numero(datos.get("precio"))
    c = usuario.cartera
    if c is None or precio is None or precio <= 0:
        return None
    precio = round(precio, 2)
    if tipo == "SUBE_A" and precio > c.precio_actual:
        return Accion("ALERTA", f"Avisarme si sube a {usdt(precio)} USDT", alerta=AlertaPropuesta("SUBE_A", precio))
    if tipo == "BAJA_A" and precio < c.precio_actual:
        return Accion("ALERTA", f"Avisarme si baja a {usdt(precio)} USDT", alerta=AlertaPropuesta("BAJA_A", precio))
    return None
