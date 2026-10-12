"""Lectura de la liga de inversores desde la base de datos."""

from bitcoinai.basedatos import BaseDatos
from bitcoinai.estructuras import Lista
from bitcoinai.simulacion.ranking import Participante


def participantes_activos(bd: BaseDatos, precio: float) -> Lista[Participante]:
    """Cada usuario que ya ejecutó al menos una orden (pagó comisión), valorado a ``precio``.

    Solo lee la cartera de la tabla ``simulaciones``: ni nombres ni datos personales.
    Quien nunca operó no entra (empataría en 0 % con todos los demás). O(n).
    """
    participantes: Lista[Participante] = Lista()
    for fila in bd.todas("SELECT usuario_id, saldo_inicial, saldo_usdt, btc FROM simulaciones"
                         " WHERE comisiones_pagadas > 0 ORDER BY usuario_id"):
        valor = float(fila["saldo_usdt"]) + float(fila["btc"]) * precio
        inicial = float(fila["saldo_inicial"])
        participantes.agregar(Participante(int(fila["usuario_id"]), valor, (valor - inicial) / inicial))
    return participantes
