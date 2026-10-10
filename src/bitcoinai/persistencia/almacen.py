"""Almacén de la simulación en archivos JSON."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from bitcoinai.estructuras import Lista
from bitcoinai.persistencia import conversor
from bitcoinai.persistencia.conversor import DatosDanadosError
from bitcoinai.simulacion import DatosCartera, EstadoOrden, EstadoSimulacion, Evento, Orden

CARTERA = "cartera.json"
ORDENES = "ordenes.json"
HISTORIAL = "historial.json"

_VERSION = 1
_INTENTOS_AL_MOVER = 5

LOG = logging.getLogger("bitcoinai.persistencia")


class AlmacenArchivos:
    """Guarda el estado de la simulación en tres archivos JSON dentro de un directorio
    (variable de entorno ``DATA_DIR``, por defecto ``./data``):

    - ``cartera.json``: saldo, BTC y costo de la posición.
    - ``ordenes.json``: cola de pendientes (en orden de llegada), registro, ids en
      orden de creación (para deshacer) y el próximo id.
    - ``historial.json``: eventos del más viejo al más nuevo.

    **Escritura atómica:** cada archivo se escribe primero en uno temporal (``.tmp``)
    y luego se mueve sobre el definitivo con ``os.replace``. Si el proceso muere a
    mitad de una escritura, queda el archivo anterior completo, nunca uno a medias.

    **Carga tolerante:** si un archivo está dañado, se aparta con otro nombre
    (``.danado-<momento>``) para poder revisarlo, se registra una advertencia y se
    empieza limpio. Cartera y órdenes se cargan juntas (si una falla, ninguna se usa,
    para no mezclar estados incoherentes); el historial va aparte.

    Nota: el disco de un contenedor de Railway se borra en cada despliegue; para
    conservar los datos hay que montar un volumen y apuntar ``DATA_DIR`` a él.
    """

    def __init__(self, directorio: str | os.PathLike[str]) -> None:
        self.directorio = Path(directorio)

    # ---------- guardar ----------

    def guardar(self, estado: EstadoSimulacion) -> None:
        """Guarda los tres archivos, cada uno de forma atómica. Complejidad: O(n).

        Raises:
            OSError: si no se pudo escribir.
        """
        self.directorio.mkdir(parents=True, exist_ok=True)
        # Las listas de Python solo aparecen aquí, en la frontera JSON.
        self._escribir_atomico(ORDENES, {
            "version": _VERSION,
            "siguienteId": estado.siguiente_id,
            "pendientes": [conversor.orden_a_json(o) for o in estado.pendientes],
            "registro": [conversor.orden_a_json(o) for o in estado.registro],
            "creadas": [i for i in estado.creadas],
        })
        self._escribir_atomico(CARTERA, {
            "version": _VERSION,
            "cartera": None if estado.cartera is None else conversor.cartera_a_json(estado.cartera),
        })
        self._escribir_atomico(HISTORIAL, {
            "version": _VERSION,
            "eventos": [conversor.evento_a_json(e) for e in estado.eventos],
        })

    def _escribir_atomico(self, nombre: str, contenido: dict[str, Any]) -> None:
        destino = self.directorio / nombre
        temporal = self.directorio / f"{nombre}.tmp"
        temporal.write_text(json.dumps(contenido, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        for intento in range(1, _INTENTOS_AL_MOVER + 1):
            try:
                os.replace(temporal, destino)
                return
            except PermissionError:
                # En Windows otro programa (antivirus, OneDrive) puede tener el archivo abierto un instante.
                if intento == _INTENTOS_AL_MOVER:
                    raise
                time.sleep(0.02 * intento)

    # ---------- cargar ----------

    def cargar(self) -> EstadoSimulacion | None:
        """Carga el estado guardado. Nunca falla: si algo está dañado lo aparta,
        registra una advertencia y lo trata como si no existiera.

        Returns:
            El estado, o None si no había nada utilizable.
        """
        cartera: DatosCartera | None = None
        siguiente_id = 1
        pendientes: Lista[Orden] = Lista()
        registro: Lista[Orden] = Lista()
        creadas: Lista[int] = Lista()

        hay_cartera = (self.directorio / CARTERA).exists()
        hay_ordenes = (self.directorio / ORDENES).exists()
        if hay_cartera or hay_ordenes:
            try:
                if not (hay_cartera and hay_ordenes):
                    falta = ORDENES if hay_cartera else CARTERA
                    raise DatosDanadosError(f"falta {falta} y no se puede usar el otro solo")
                raiz_cartera = self._leer(CARTERA)
                raiz_ordenes = self._leer(ORDENES)
                cartera = conversor.cartera(raiz_cartera.get("cartera"))
                siguiente_id = conversor.entero(raiz_ordenes, "siguienteId")
                for valor in conversor.lista(raiz_ordenes, "pendientes"):
                    orden = conversor.orden(valor)
                    if orden.estado is not EstadoOrden.PENDIENTE:
                        raise DatosDanadosError(f"la orden #{orden.id} está en la cola sin estar pendiente")
                    pendientes.agregar(orden)
                for valor in conversor.lista(raiz_ordenes, "registro"):
                    registro.agregar(conversor.orden(valor))
                for valor in conversor.lista(raiz_ordenes, "creadas"):
                    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
                        raise DatosDanadosError(f"id inválido en 'creadas': {valor}")
                    creadas.agregar(valor)
            except (OSError, ValueError, DatosDanadosError) as error:
                LOG.warning("Cartera y órdenes guardadas inutilizables (%s); "
                            "se empieza con cartera y órdenes limpias.", error)
                self._apartar(CARTERA)
                self._apartar(ORDENES)
                cartera, siguiente_id = None, 1
                pendientes, registro, creadas = Lista(), Lista(), Lista()

        eventos: Lista[Evento] = Lista()
        if (self.directorio / HISTORIAL).exists():
            try:
                for valor in conversor.lista(self._leer(HISTORIAL), "eventos"):
                    eventos.agregar(conversor.evento(valor))
            except (OSError, ValueError, DatosDanadosError) as error:
                LOG.warning("Historial guardado inutilizable (%s); se empieza sin historial.", error)
                self._apartar(HISTORIAL)
                eventos = Lista()

        if cartera is None and eventos.esta_vacia():
            return None
        return EstadoSimulacion(cartera, siguiente_id, pendientes, registro, creadas, eventos)

    def _leer(self, nombre: str) -> dict[str, Any]:
        """Lee un archivo y valida su versión. ``json`` lanza ValueError si el texto no es JSON."""
        texto = (self.directorio / nombre).read_text(encoding="utf-8")
        raiz = conversor.mapa(json.loads(texto), nombre)
        if conversor.entero_opcional(raiz, "version") != _VERSION:
            raise DatosDanadosError(f"{nombre} tiene una versión desconocida")
        return raiz

    def _apartar(self, nombre: str) -> None:
        """Renombra un archivo dañado para no perderlo ni volver a leerlo."""
        archivo = self.directorio / nombre
        if not archivo.exists():
            return
        apartado = self.directorio / f"{nombre}.danado-{int(time.time() * 1000)}"
        try:
            os.replace(archivo, apartado)
            LOG.warning("Archivo dañado apartado como %s", apartado.name)
        except OSError as error:
            LOG.warning("No se pudo apartar %s: %s", archivo, error)
