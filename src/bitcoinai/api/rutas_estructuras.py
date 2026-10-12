"""Las estructuras de datos, a la vista (pantalla "Cómo funciona").

- GET /api/estructuras: cómo están ahora mismo las estructuras reales de tu
  simulación (cola de pendientes, pila del historial, pila de deshacer, registro)
  y las del servidor (tabla hash de usuarios, cola circular de precios y trie de
  la búsqueda). Exige sesión; de los demás usuarios solo se muestran cantidades.
- POST /api/estructuras/demo: corre operaciones sobre una estructura nueva y
  devuelve cómo queda después de cada una. Es pública y no guarda nada.
"""

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from bitcoinai.api.configuracion import Configuracion
from bitcoinai.api.demo_estructuras import DemoInvalidaError, Operacion, ejecutar
from bitcoinai.api.errores import ApiError
from bitcoinai.api.rutas_cuentas import Cookies, sesion_de
from bitcoinai.busqueda import Buscador
from bitcoinai.mercado import PreciosRecientes
from bitcoinai.simulacion import GestorSimulaciones
from bitcoinai.usuarios.servicio import ServicioCuentas

MOSTRAR = 10
"""Cuántos elementos de cada estructura del usuario se muestran como máximo."""


class CuerpoOperacion(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    operacion: str
    valor: int | str | None = None


class CuerpoDemo(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    estructura: str
    operaciones: list[CuerpoOperacion]


def crear_rutas_estructuras(gestor: GestorSimulaciones | None, cuentas: ServicioCuentas | None,
                            recientes: PreciosRecientes, buscador: Buscador, config: Configuracion) -> APIRouter:
    rutas = APIRouter()
    cookies = Cookies(config)

    @rutas.post("/api/estructuras/demo")
    def demo(cuerpo: CuerpoDemo) -> dict[str, Any]:
        """Paso a paso con el código real de ``bitcoinai.estructuras``."""
        try:
            pasos = ejecutar(cuerpo.estructura, (Operacion(o.operacion, o.valor) for o in cuerpo.operaciones))
        except DemoInvalidaError as error:
            raise ApiError(400, str(error)) from None
        return {"estructura": cuerpo.estructura, "pasos": pasos}

    if gestor is None or cuentas is None:
        return rutas

    @rutas.get("/api/estructuras")
    def actuales(peticion: Request) -> dict[str, Any]:
        """Foto de las estructuras reales. Leerlas no las cambia (cola rotada, pilas con auxiliar)."""
        usuario, _ = sesion_de(peticion, cuentas, cookies)
        libro = gestor.libro(usuario.id)
        en_cola, en_registro, en_historial, en_deshacer = libro.tamanios()
        pendientes = [
            {"id": o.id, "tipo": o.tipo.name, "monto": o.monto, "todo": o.todo}
            for o in libro.ordenes() if o.estado.name in ("PENDIENTE", "PROCESANDO")
        ][:MOSTRAR]
        eventos = [{"tipo": e.tipo.name, "idOrden": e.id_orden, "momento": e.momento}
                   for e in libro.historial(MOSTRAR)]
        capacidad, cargadas, longitudes = gestor.reparto_de_la_tabla()
        frente, en_anillo, casillas = recientes.estado_del_anillo()
        return {
            "cola": {"tamanio": en_cola, "ordenes": pendientes},
            "pila": {"tamanio": en_historial, "eventos": eventos},
            "pilaDeshacer": {"tamanio": en_deshacer, "ids": list(libro.pila_deshacer(MOSTRAR))},
            "lista": {"tamanio": en_registro},
            "tablaHash": {"capacidad": capacidad, "tamanio": cargadas, "factorCarga": cargadas / capacidad,
                          "longitudes": list(longitudes)},
            "colaCircular": {"capacidad": recientes.capacidad(), "frente": frente, "tamanio": en_anillo,
                             "casillas": list(casillas)},
            "trie": {"palabras": buscador.palabras_indexadas(), "nodos": buscador.nodos_del_trie()},
        }

    return rutas
