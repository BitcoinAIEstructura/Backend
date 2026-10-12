"""Tiempo real con Server-Sent Events (SSE): publicador, suscriptores y la respuesta de /api/stream."""

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from bitcoinai.api.errores import ApiError
from bitcoinai.api.serializacion import cartera_a_json, decision_a_json, orden_a_json
from bitcoinai.estrategia import Decision
from bitcoinai.estructuras import Cola, Lista, ListaDoble, NodoDoble
from bitcoinai.mercado import FuenteDeMercado, PreciosRecientes
from bitcoinai.simulacion import EstadoCartera, Orden

MAXIMO_POR_DEFECTO = 50
"""Conexiones simultáneas permitidas por defecto (``MAX_STREAMS``)."""

BUZON_MAXIMO = 1000
"""Mensajes sin leer que se toleran por cliente; si se pasa, el cliente es demasiado lento y se lo quita."""

INICIO = "retry: 5000\n: conectado\n\n"
LATIDO = ": latido\n\n"

LOG = logging.getLogger("bitcoinai.api")


class Suscriptor:
    """Un cliente conectado a /api/stream.

    Tiene un buzón (``Cola[str]``) con los mensajes que todavía no se le enviaron:
    el publicador encola desde cualquier hilo (O(1)) y la respuesta HTTP desencola
    en el hilo del servidor (O(1)), en orden FIFO. Un candado protege el buzón y,
    al encolar, se despierta a la respuesta con ``loop.call_soon_threadsafe``.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, limite: int = BUZON_MAXIMO,
                 usuario_id: int | None = None) -> None:
        self._loop = loop
        self.usuario_id = usuario_id  # None: anónimo, solo recibe los eventos públicos (precio)
        self._limite = limite
        self._buzon: Cola[str] = Cola()
        self._candado = threading.Lock()
        self._aviso = asyncio.Event()
        self._cerrado = False
        self.nodo: NodoDoble[Suscriptor] | None = None  # su lugar en la lista del publicador

    @property
    def cerrado(self) -> bool:
        return self._cerrado

    def entregar(self, texto: str) -> bool:
        """Deja un mensaje en el buzón. Nunca bloquea. Complejidad: O(1).

        Returns:
            False si el cliente ya no puede recibir (buzón lleno o servidor cerrado).
        """
        with self._candado:
            if self._cerrado:
                return False
            if self._buzon.tamanio() >= self._limite:
                return False
            self._buzon.encolar(texto)
        return self._despertar()

    def cerrar(self) -> None:
        """Marca el suscriptor como cerrado; la respuesta termina en cuanto lo nota."""
        with self._candado:
            self._cerrado = True
        self._despertar()

    def _despertar(self) -> bool:
        try:
            self._loop.call_soon_threadsafe(self._aviso.set)
            return True
        except RuntimeError:  # el bucle del servidor ya terminó
            return False

    async def siguiente(self, espera: float) -> str | None:
        """Próximo mensaje del buzón; espera hasta ``espera`` segundos.

        Returns:
            El mensaje, o None si no llegó nada a tiempo o si se cerró.
        """
        while True:
            with self._candado:
                if not self._buzon.esta_vacia():
                    return self._buzon.desencolar()
                if self._cerrado:
                    return None
                # Se limpia con el candado tomado: un mensaje que llegue después programa
                # un set() posterior, así que no se pierde el aviso.
                self._aviso.clear()
            try:
                await asyncio.wait_for(self._aviso.wait(), espera)
            except TimeoutError:
                return None


class Publicador:
    """Publica eventos en tiempo real a los clientes de ``/api/stream``.

    Cada evento se envía así::

        event: precio
        data: {"simbolo":"BTCUSDT","precio":83097.08,"momento":1791417600000}

    Eventos: ``precio`` (cada 5 s, solo si hay alguien conectado), ``orden``,
    ``cartera`` y ``senal`` (los publican el libro de órdenes y el bot a través de la
    interfaz ``PublicadorEventos``), más un comentario ``: latido`` cada 15 s, para
    que los proxies no corten la conexión por inactividad.

    **Uso de la lista doble:** los suscriptores están en una ``ListaDoble[Suscriptor]``.
    Al agregar uno se guarda su nodo (``agregar_final_nodo``); cuando se desconecta o
    se queda atrás, se lo quita con ``eliminar_nodo(nodo)`` en O(1): el nodo ya
    conoce a su anterior y a su siguiente, así que basta con unirlos, sin recorrer la
    lista. Con una lista simple habría que recorrerla para hallar el anterior (O(n)).

    Concurrencia: la lista la protege un candado. ``publicar`` solo deja el texto en
    el buzón de cada suscriptor, así nunca bloquea a quien lo llama (el libro de
    órdenes lo llama con su candado tomado) y los eventos llegan en orden.
    """

    def __init__(self, fuente: FuenteDeMercado, simbolo: str, maximo: int = MAXIMO_POR_DEFECTO,
                 periodo_precio: float = 5.0, periodo_latido: float = 15.0) -> None:
        """Raises: ValueError si el máximo es menor que 1."""
        if maximo < 1:
            raise ValueError("El máximo de conexiones debe ser al menos 1")
        self._fuente = fuente
        self._simbolo = simbolo
        self._maximo = maximo
        self._periodo_precio = periodo_precio
        self._periodo_latido = periodo_latido
        self._suscriptores: ListaDoble[Suscriptor] = ListaDoble()
        self._candado = threading.Lock()
        self._parar: threading.Event | None = None
        self._recientes: PreciosRecientes | None = None

    def usar_recientes(self, recientes: PreciosRecientes) -> None:
        """Cada precio publicado se anota también en la cola circular de precios recientes."""
        self._recientes = recientes

    # ---------- ciclo de vida ----------

    def iniciar(self) -> None:
        """Empieza a publicar el precio y el latido periódicamente (en un hilo propio)."""
        with self._candado:
            if self._parar is not None:
                return
            parar = threading.Event()
            self._parar = parar
        threading.Thread(target=self._bucle, args=(parar,), name="sse-periodico", daemon=True).start()

    def detener(self) -> None:
        """Detiene el precio y cierra todas las conexiones (para apagar el servidor). O(n)."""
        with self._candado:
            if self._parar is not None:
                self._parar.set()
                self._parar = None
            for suscriptor in self._suscriptores:
                suscriptor.cerrar()
            self._suscriptores.vaciar()

    def _bucle(self, parar: threading.Event) -> None:
        proximo_precio = time.monotonic() + self._periodo_precio
        proximo_latido = time.monotonic() + self._periodo_latido
        while not parar.wait(max(0.0, min(proximo_precio, proximo_latido) - time.monotonic())):
            ahora = time.monotonic()
            if ahora >= proximo_precio:
                self.publicar_precio()
                proximo_precio = ahora + self._periodo_precio
            if ahora >= proximo_latido:
                self.enviar_latido()
                proximo_latido = ahora + self._periodo_latido

    # ---------- suscriptores ----------

    def suscribir(self, loop: asyncio.AbstractEventLoop, usuario_id: int | None = None) -> Suscriptor:
        """Registra un cliente nuevo; con ``usuario_id`` recibe además sus eventos privados. O(1).

        Raises:
            ApiError: 503 si ya se alcanzó el máximo de conexiones.
        """
        suscriptor = Suscriptor(loop, usuario_id=usuario_id)
        with self._candado:
            if self._suscriptores.tamanio() >= self._maximo:
                raise ApiError(503, f"Demasiadas conexiones de tiempo real abiertas (máximo {self._maximo}); "
                                    "intenta más tarde")
            suscriptor.nodo = self._suscriptores.agregar_final_nodo(suscriptor)
        return suscriptor

    def desuscribir(self, suscriptor: Suscriptor) -> bool:
        """Quita un suscriptor por su nodo, sin recorrer la lista, y lo cierra.

        Llamarlo más de una vez es seguro. Complejidad: O(1).

        Returns:
            True si estaba en la lista.
        """
        with self._candado:
            quitado = self._suscriptores.eliminar_nodo(suscriptor.nodo)
        suscriptor.cerrar()
        return quitado

    def cantidad_suscriptores(self) -> int:
        """Cuántos clientes están conectados. Complejidad: O(1)."""
        with self._candado:
            return self._suscriptores.tamanio()

    # ---------- publicación ----------

    def publicar(self, tipo: str, datos: object) -> None:
        """Envía un evento público a todos los clientes. No bloquea. Complejidad: O(n) con n clientes.

        Se copia la lista con el candado tomado y se entrega sin él; a quien no pueda
        recibir se lo quita por su nodo en O(1).
        """
        self._difundir(f"event: {tipo}\ndata: {_a_texto_json(datos)}\n\n")

    def publicar_a(self, usuario_id: int, tipo: str, datos: object) -> None:
        """Envía un evento privado (sus órdenes, su cartera, su señal) solo a las conexiones de ese usuario."""
        self._difundir(f"event: {tipo}\ndata: {_a_texto_json(datos)}\n\n", usuario_id)

    def enviar_latido(self) -> None:
        """Comentario de latido (las líneas que empiezan con ":" el navegador las ignora)."""
        self._difundir(LATIDO)

    def _difundir(self, texto: str, usuario_id: int | None = None) -> None:
        """A todos, o solo a los de ``usuario_id``."""
        copia: Lista[Suscriptor] = Lista()
        with self._candado:
            for suscriptor in self._suscriptores:
                if usuario_id is None or suscriptor.usuario_id == usuario_id:
                    copia.agregar(suscriptor)
        for suscriptor in copia:
            if not suscriptor.entregar(texto):
                LOG.info("Cliente de tiempo real quitado: no recibe los mensajes a tiempo")
                self.desuscribir(suscriptor)

    def publicar_precio(self) -> None:
        """Publica el precio actual, solo si hay alguien escuchando. Si la fuente falla, lo salta."""
        if self.cantidad_suscriptores() == 0:
            return
        try:
            precio = self._fuente.obtener_precio_actual(self._simbolo)
        except Exception as error:
            LOG.debug("No se pudo publicar el precio: %s", error)
            return
        momento = int(time.time() * 1000)
        if self._recientes is not None:
            self._recientes.registrar(momento, precio)
        self.publicar("precio", {"simbolo": self._simbolo, "precio": precio, "momento": momento})

    async def mensajes(self, suscriptor: Suscriptor) -> AsyncIterator[str]:
        """Lo que se le escribe a un cliente: el saludo y después lo que llegue a su buzón."""
        yield INICIO
        while True:
            mensaje = await suscriptor.siguiente(1.0)
            if mensaje is not None:
                yield mensaje
            elif suscriptor.cerrado:
                return


class PublicadorDeUsuario:
    """Adaptador: un ``PublicadorEventos`` para el libro y el bot de un usuario.

    El libro llama ``publicar("orden", …)`` sin saber de quién es; esto lo convierte
    en un evento privado para ese usuario.
    """

    def __init__(self, publicador: Publicador, usuario_id: int) -> None:
        self._publicador = publicador
        self.usuario_id = usuario_id

    def publicar(self, tipo: str, datos: object) -> None:
        self._publicador.publicar_a(self.usuario_id, tipo, datos)


class RespuestaStream(StreamingResponse):
    """Respuesta de ``GET /api/stream``. Pase lo que pase (fin normal, desconexión o
    error al escribir), al terminar quita al suscriptor del publicador."""

    def __init__(self, publicador: Publicador, suscriptor: Suscriptor) -> None:
        super().__init__(publicador.mensajes(suscriptor), media_type="text/event-stream; charset=utf-8",
                         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        self._publicador = publicador
        self._suscriptor = suscriptor

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self._publicador.desuscribir(self._suscriptor)


def _a_texto_json(datos: object) -> str:
    """JSON en una sola línea, con las mismas claves que la API."""
    valor: Any
    if isinstance(datos, Orden):
        valor = orden_a_json(datos)
    elif isinstance(datos, EstadoCartera):
        valor = cartera_a_json(datos)
    elif isinstance(datos, Decision):
        valor = decision_a_json(datos)
    else:
        valor = datos
    return json.dumps(valor, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
