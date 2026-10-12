"""GET /api/liga: la liga de inversores (los 10 mejores por rentabilidad y tu puesto).

Exige sesión. Nadie aparece con su nombre: cada uno tiene un alias estable.
"""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.rutas_cuentas import Cookies, sesion_de
from bitcoinai.estructuras import Lista
from bitcoinai.mercado import FuenteDeMercado
from bitcoinai.simulacion.ranking import Clasificado, Participante, alias_publico, mejores, posicion_de
from bitcoinai.usuarios.servicio import ServicioCuentas


def crear_rutas_liga(leer_participantes: Callable[[float], Lista[Participante]], fuente: FuenteDeMercado,
                     simbolo: str, cuentas: ServicioCuentas, config: Configuracion) -> APIRouter:
    """Crea el router de la liga. ``leer_participantes(precio)`` trae la cartera de cada usuario activo."""
    rutas = APIRouter()
    cookies = Cookies(config)

    def a_json(c: Clasificado, usuario_id: int) -> dict[str, Any]:
        return {
            "posicion": c.posicion,
            "alias": alias_publico(c.participante.usuario_id),
            "rentabilidad": c.participante.rentabilidad,
            "valorTotal": c.participante.valor_total,
            "esTuyo": c.participante.usuario_id == usuario_id,
        }

    @rutas.get("/api/liga")
    def liga(peticion: Request) -> dict[str, Any]:
        """Los 10 mejores (montículo de tamaño 10, O(n log 10)) y el puesto de quien pregunta."""
        usuario, _ = sesion_de(peticion, cuentas, cookies)
        precio = fuente.obtener_precio_actual(simbolo)
        participantes = leer_participantes(precio)
        tuyo = posicion_de(participantes, usuario.id)
        return {
            "precio": precio,
            "participantes": participantes.tamanio(),
            "mejores": [a_json(c, usuario.id) for c in mejores(participantes)],
            "tu": None if tuyo is None else a_json(tuyo, usuario.id),
        }

    return rutas
