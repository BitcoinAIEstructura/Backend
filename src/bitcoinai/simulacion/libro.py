"""Libro de órdenes simulado (paper trading). Nunca toca una cuenta real."""

import dataclasses
import logging
import math
import threading
import time
from collections.abc import Callable

from bitcoinai.estructuras import Cola, Lista, Pila
from bitcoinai.mercado import FuenteDeMercado
from bitcoinai.simulacion.cartera import Cartera, Ejecucion, EstadoCartera
from bitcoinai.simulacion.interfaces import AlmacenSimulacion, EstadoSimulacion, PublicadorEventos, SinPublicar
from bitcoinai.simulacion.modelo import (
    EstadoOrden,
    Evento,
    OperacionInvalidaError,
    OperacionRechazadaError,
    Orden,
    OrdenNoEncontradaError,
    TipoEvento,
    TipoOrden,
)

COMISION_POR_DEFECTO = 0.001
"""Comisión por defecto: 0,1 %."""

EVENTOS_GUARDADOS_MAXIMO = 2000
"""Cuántos eventos del historial se guardan en disco como máximo (los más recientes)."""

LOG = logging.getLogger("bitcoinai.simulacion")


def _ahora_ms() -> int:
    return int(time.time() * 1000)


class LibroDeOrdenes:
    """Libro de órdenes simulado.

    Estructuras:
        - ``Cola[Orden]`` de pendientes: se ejecutan en orden de llegada (FIFO).
        - ``Lista[Orden]`` registro: órdenes ya ejecutadas, canceladas o rechazadas,
          en el orden en que terminaron.
        - ``Pila[Evento]`` historial: el evento más reciente queda arriba.
        - ``Pila[int]`` con los ids en orden de creación, para deshacer la última.

    Concurrencia: el bot y las peticiones HTTP lo usan desde hilos distintos. Las
    estructuras no son sincronizadas; las protege un candado (``_candado``) que se
    toma solo mientras se tocan y nunca durante una llamada de red. Un segundo
    candado (``_candado_proceso``) hace que las órdenes se procesen de a una, así
    se respeta el orden FIFO aunque dos hilos procesen a la vez.

    Tiempo real y persistencia (opcionales): avisa cada cambio a un
    ``PublicadorEventos`` y guarda el estado en un ``AlmacenSimulacion`` después de
    cada cambio. Ninguno de los dos depende de HTTP ni de archivos aquí.
    """

    def __init__(self, cartera: Cartera, fuente: FuenteDeMercado, simbolo: str,
                 comision: float = COMISION_POR_DEFECTO, reloj: Callable[[], int] = _ahora_ms) -> None:
        """Raises: ValueError si la comisión no está en [0, 1)."""
        if not 0 <= comision < 1:
            raise ValueError(f"La comisión debe estar entre 0 y 1: {comision}")
        self._cartera = cartera
        self._fuente = fuente
        self._simbolo = simbolo
        self._comision = comision
        self._reloj = reloj
        self._candado = threading.RLock()
        self._candado_proceso = threading.Lock()
        self._pendientes: Cola[Orden] = Cola()
        self._registro: Lista[Orden] = Lista()
        self._eventos: Pila[Evento] = Pila()
        self._creadas: Pila[int] = Pila()
        self._siguiente_id = 1
        self._en_proceso: Orden | None = None
        self._publicador: PublicadorEventos = SinPublicar()
        self._almacen: AlmacenSimulacion | None = None  # protegido por _candado

    # ---------- tiempo real y persistencia ----------

    def usar_publicador(self, publicador: PublicadorEventos) -> None:
        """A quién avisar: "orden" cuando una orden cambia de estado y "cartera" cuando cambia el saldo o el BTC."""
        self._publicador = publicador

    def usar_almacen(self, almacen: AlmacenSimulacion) -> bool:
        """Carga el estado guardado (si hay) y a partir de ahora guarda después de cada cambio.

        Reconstruye las estructuras en el mismo orden: la cola con el orden de
        llegada, y las pilas con el elemento más reciente arriba.

        Returns:
            True si se recuperó un estado guardado.
        """
        guardado = almacen.cargar()
        with self._candado:
            if guardado is not None:
                self._restaurar(guardado)
            self._almacen = almacen
            return guardado is not None

    def _restaurar(self, estado: EstadoSimulacion) -> None:
        """Reemplaza el estado actual por el guardado. Se llama con el candado tomado. O(n)."""
        if estado.cartera is not None:
            self._cartera = Cartera.desde_datos(estado.cartera)
        mayor_id = 0
        self._pendientes.vaciar()
        for orden in estado.pendientes:
            self._pendientes.encolar(orden)  # la primera guardada vuelve a ser el frente
            mayor_id = max(mayor_id, orden.id)
        self._registro.vaciar()
        for orden in estado.registro:
            self._registro.agregar(orden)
            mayor_id = max(mayor_id, orden.id)
        self._creadas.vaciar()
        for id_orden in estado.creadas:
            self._creadas.apilar(id_orden)  # la última guardada queda en el tope
        self._eventos.vaciar()
        for evento in estado.eventos:
            self._eventos.apilar(evento)  # el evento más reciente queda arriba
        self._siguiente_id = max(estado.siguiente_id, mayor_id + 1)

    def _instantanea(self) -> EstadoSimulacion:
        """Foto para guardar. Se llama con el candado tomado. Complejidad: O(n)."""
        pendientes: Lista[Orden] = Lista()
        if self._en_proceso is not None:
            # Si el servidor se apaga a mitad de un proceso, la orden vuelve al frente al recargar.
            pendientes.agregar(self._en_proceso.con_estado(EstadoOrden.PENDIENTE, None))
        for _ in range(self._pendientes.tamanio()):  # rotar la cola: queda igual tras n vueltas
            orden = self._pendientes.desencolar()
            self._pendientes.encolar(orden)
            pendientes.agregar(orden)
        registro: Lista[Orden] = Lista()
        for orden in self._registro:
            registro.agregar(orden)
        todos = _de_abajo_hacia_arriba(self._eventos)
        recientes: Lista[Evento] = Lista()
        saltar = max(0, todos.tamanio() - EVENTOS_GUARDADOS_MAXIMO)
        for indice, evento in enumerate(todos):
            if indice >= saltar:
                recientes.agregar(evento)
        return EstadoSimulacion(self._cartera.datos(), self._siguiente_id, pendientes, registro,
                                _de_abajo_hacia_arriba(self._creadas), recientes)

    def _guardar(self) -> None:
        """Guarda si hay almacén. Un fallo al guardar no deshace la operación: se registra y se sigue."""
        if self._almacen is None:
            return
        try:
            self._almacen.guardar(self._instantanea())
        except Exception as error:
            LOG.warning("No se pudo guardar el estado de la simulación: %s", error)

    # ---------- crear ----------

    def crear_compra(self, monto: float, motivo: str | None = None) -> Orden:
        """Orden de compra por un monto en USDT."""
        return self.crear_orden(TipoOrden.COMPRA, monto, False, motivo)

    def crear_venta(self, monto: float, motivo: str | None = None) -> Orden:
        """Orden de venta por un monto en USDT."""
        return self.crear_orden(TipoOrden.VENTA, monto, False, motivo)

    def crear_venta_total(self, motivo: str | None = None) -> Orden:
        """Orden de venta de todo el BTC que haya al ejecutarse."""
        return self.crear_orden(TipoOrden.VENTA, None, True, motivo)

    def crear_orden(self, tipo: TipoOrden, monto: float | None, todo: bool, motivo: str | None) -> Orden:
        """Crea una orden y la pone al final de la cola.

        Complejidad: O(1).

        Raises:
            ValueError: si la combinación de datos es inválida.
        """
        if todo:
            if tipo is not TipoOrden.VENTA or monto is not None:
                raise ValueError("'todo' solo se usa en ventas y sin monto")
        elif monto is None or not (monto > 0 and math.isfinite(monto)):
            raise ValueError("El monto debe ser un número mayor que 0")
        motivo_final = motivo.strip() if motivo and motivo.strip() else "manual"
        with self._candado:
            orden = Orden(self._siguiente_id, tipo, monto, todo, EstadoOrden.PENDIENTE, self._reloj(),
                          motivo=motivo_final)
            self._siguiente_id += 1
            self._pendientes.encolar(orden)
            self._creadas.apilar(orden.id)
            que = "vender todo el BTC" if todo else f"{monto:.2f} USDT"
            self._apilar_evento(TipoEvento.ORDEN_CREADA, orden.id,
                                f"Orden #{orden.id} de {tipo.name} por {que} creada ({motivo_final}).")
            self._publicador.publicar("orden", orden)
            self._guardar()
            return orden

    # ---------- procesar ----------

    def procesar_siguiente(self) -> Orden | None:
        """Toma la orden del frente de la cola y la ejecuta al precio actual con comisión,
        o la rechaza con el motivo si no alcanza el saldo o el BTC.

        Pasos: (1) con el candado, la saca de la cola y la marca PROCESANDO; (2) sin
        el candado, consulta el precio (puede tardar); (3) con el candado, la ejecuta
        contra la cartera y la pasa al registro. Si el precio no se puede obtener, la
        orden vuelve al frente de la cola, PENDIENTE, y se propaga el error.
        Complejidad: O(1) más la consulta del precio (O(n) solo si hay que devolverla).

        Returns:
            La orden procesada, o None si no había pendientes.

        Raises:
            MercadoError: si falla la consulta del precio.
        """
        with self._candado_proceso:
            with self._candado:
                if self._pendientes.esta_vacia():
                    return None
                pendiente = self._pendientes.desencolar()
                self._en_proceso = pendiente.con_estado(EstadoOrden.PROCESANDO, None)
                self._publicador.publicar("orden", self._en_proceso)
            try:
                precio = self._fuente.obtener_precio_actual(self._simbolo)
            except Exception:
                with self._candado:
                    self._en_proceso = None
                    self._devolver_al_frente(pendiente)
                    self._publicador.publicar("orden", pendiente)
                    self._guardar()
                raise
            with self._candado:
                resultado = self._ejecutar(self._en_proceso, precio)
                self._en_proceso = None
                self._registro.agregar(resultado)
                self._publicador.publicar("orden", resultado)
                if resultado.estado is EstadoOrden.EJECUTADA:
                    self._publicador.publicar("cartera", self._cartera.estado(precio))
                self._guardar()
                return resultado

    def _ejecutar(self, orden: Orden, precio: float) -> Orden:
        """Ejecuta (o rechaza) contra la cartera. Se llama con el candado tomado."""
        ahora = self._reloj()
        try:
            ejecucion: Ejecucion
            if orden.tipo is TipoOrden.COMPRA:
                assert orden.monto is not None
                ejecucion = self._cartera.comprar(orden.monto, precio, self._comision)
            elif orden.todo:
                ejecucion = self._cartera.vender_todo(precio, self._comision)
            else:
                assert orden.monto is not None
                ejecucion = self._cartera.vender(orden.monto, precio, self._comision)
        except OperacionRechazadaError as error:
            self._apilar_evento(TipoEvento.ORDEN_RECHAZADA, orden.id, f"Orden #{orden.id} rechazada: {error}.")
            return dataclasses.replace(orden, estado=EstadoOrden.RECHAZADA, ejecutada_en=ahora,
                                       precio_ejecucion=precio, detalle=str(error))
        verbo = "Compró" if orden.tipo is TipoOrden.COMPRA else "Vendió"
        detalle = (f"{verbo} {ejecucion.cantidad_btc:.8f} BTC a {precio:.2f} por {ejecucion.monto_usdt:.2f} USDT "
                   f"(comisión {ejecucion.comision:.2f} USDT).")
        self._apilar_evento(TipoEvento.ORDEN_EJECUTADA, orden.id, f"Orden #{orden.id} ejecutada: {detalle}")
        return dataclasses.replace(
            orden, estado=EstadoOrden.EJECUTADA, ejecutada_en=ahora, precio_ejecucion=precio,
            cantidad_btc=ejecucion.cantidad_btc, comision=ejecucion.comision,
            monto=ejecucion.monto_usdt if orden.todo else orden.monto, detalle=detalle)

    def _devolver_al_frente(self, orden: Orden) -> None:
        """Vuelve a poner una orden al frente. Una cola solo agrega al final, así que se
        pasa todo a una auxiliar, se encola la orden y luego el resto. Complejidad: O(n)."""
        resto: Cola[Orden] = Cola()
        while not self._pendientes.esta_vacia():
            resto.encolar(self._pendientes.desencolar())
        self._pendientes.encolar(orden)
        while not resto.esta_vacia():
            self._pendientes.encolar(resto.desencolar())

    # ---------- cancelar y deshacer ----------

    def cancelar(self, id_orden: int) -> Orden:
        """Cancela una orden pendiente.

        Una cola no permite sacar un elemento del medio, así que se reconstruye: se
        desencolan todas y se vuelven a encolar todas menos la cancelada. Las demás
        conservan su orden. Complejidad: O(n), con n pendientes.

        Raises:
            OrdenNoEncontradaError: si no existe.
            OperacionInvalidaError: si ya no está pendiente.
        """
        with self._candado:
            cancelada = self._quitar_de_la_cola(id_orden, EstadoOrden.CANCELADA, "Cancelada antes de ejecutarse.")
            if cancelada is None:
                raise self._no_pendiente(id_orden)
            self._apilar_evento(TipoEvento.ORDEN_CANCELADA, id_orden, f"Orden #{id_orden} cancelada.")
            self._publicador.publicar("orden", cancelada)
            self._guardar()
            return cancelada

    def deshacer_ultima_orden(self) -> Orden | None:
        """Deshace la última orden creada si sigue pendiente.

        Los ids se apilan al crearse, así que el tope de la pila es la última creada.
        Se desapila: si sigue pendiente se quita de la cola (O(n)); si no, no se hace
        nada. Llamarlo de nuevo intenta con la anterior.

        Returns:
            La orden deshecha, o None si no había ninguna o ya no estaba pendiente.
        """
        with self._candado:
            if self._creadas.esta_vacia():
                return None
            id_orden = self._creadas.desapilar()
            deshecha = self._quitar_de_la_cola(id_orden, EstadoOrden.CANCELADA, "Deshecha: era la última orden creada.")
            if deshecha is None:
                self._guardar()  # la pila de creadas cambió
                return None
            self._apilar_evento(TipoEvento.ORDEN_DESHECHA, id_orden, f"Orden #{id_orden} deshecha.")
            self._publicador.publicar("orden", deshecha)
            self._guardar()
            return deshecha

    def _quitar_de_la_cola(self, id_orden: int, estado: EstadoOrden, detalle: str) -> Orden | None:
        """Reconstruye la cola sin la orden; si estaba, la pasa al registro con el estado dado. O(n)."""
        quitada: Orden | None = None
        for _ in range(self._pendientes.tamanio()):
            orden = self._pendientes.desencolar()
            if orden.id == id_orden and quitada is None:
                quitada = orden.con_estado(estado, detalle)
            else:
                self._pendientes.encolar(orden)
        if quitada is not None:
            self._registro.agregar(quitada)
        return quitada

    def _no_pendiente(self, id_orden: int) -> Exception:
        if self._en_proceso is not None and self._en_proceso.id == id_orden:
            return OperacionInvalidaError(f"La orden #{id_orden} se está procesando y ya no se puede cancelar")
        indice = self._registro.buscar(lambda o: o.id == id_orden)
        if indice >= 0:
            estado = self._registro.obtener(indice).estado.name
            return OperacionInvalidaError(f"La orden #{id_orden} ya no está pendiente: está {estado}")
        return OrdenNoEncontradaError(id_orden)

    # ---------- consultas ----------

    def ordenes(self, estado: EstadoOrden | None = None) -> Lista[Orden]:
        """Órdenes, opcionalmente filtradas por estado: primero las pendientes en orden de
        cola, luego la que se está procesando y por último el registro.

        Para leer la cola sin perderla, se desencola cada orden y se vuelve a encolar:
        tras n vueltas queda igual que antes. Complejidad: O(n + r).
        """
        with self._candado:
            resultado: Lista[Orden] = Lista()
            for _ in range(self._pendientes.tamanio()):
                orden = self._pendientes.desencolar()
                self._pendientes.encolar(orden)
                if estado is None or orden.estado is estado:
                    resultado.agregar(orden)
            if self._en_proceso is not None and estado in (None, EstadoOrden.PROCESANDO):
                resultado.agregar(self._en_proceso)
            for orden in self._registro:
                if estado is None or orden.estado is estado:
                    resultado.agregar(orden)
            return resultado

    @property
    def comision(self) -> float:
        """Fracción de comisión que cobra cada ejecución (0,001 = 0,1 %)."""
        return self._comision

    def obtener(self, id_orden: int) -> Orden:
        """Una orden por id, en su estado actual. Complejidad: O(n + r).

        Raises:
            OrdenNoEncontradaError: si no existe.
        """
        for orden in self.ordenes():
            if orden.id == id_orden:
                return orden
        raise OrdenNoEncontradaError(id_orden)

    def cantidad_pendientes(self) -> int:
        """Cuántas órdenes esperan en la cola. Complejidad: O(1)."""
        with self._candado:
            return self._pendientes.tamanio()

    def historial(self, limite: int) -> Lista[Evento]:
        """Los eventos más recientes, del más nuevo al más viejo, sin quitarlos.

        Una pila solo deja ver el tope: se desapilan los k primeros (guardándolos en
        el resultado y en una pila auxiliar) y después se devuelven desde la
        auxiliar, que los deja en el mismo orden de antes. Complejidad: O(k).

        Raises:
            ValueError: si el límite es negativo.
        """
        if limite < 0:
            raise ValueError("El límite no puede ser negativo")
        with self._candado:
            resultado: Lista[Evento] = Lista()
            auxiliar: Pila[Evento] = Pila()
            while not self._eventos.esta_vacia() and resultado.tamanio() < limite:
                evento = self._eventos.desapilar()
                resultado.agregar(evento)
                auxiliar.apilar(evento)
            while not auxiliar.esta_vacia():
                self._eventos.apilar(auxiliar.desapilar())
            return resultado

    def pila_deshacer(self, limite: int) -> Lista[int]:
        """Los ids que "Deshacer" intentaría, del próximo al más viejo, sin quitarlos.

        Igual que ``historial``: se desapilan k a una auxiliar y se devuelven. Complejidad: O(k).
        """
        with self._candado:
            resultado: Lista[int] = Lista()
            auxiliar: Pila[int] = Pila()
            while not self._creadas.esta_vacia() and resultado.tamanio() < limite:
                id_orden = self._creadas.desapilar()
                resultado.agregar(id_orden)
                auxiliar.apilar(id_orden)
            while not auxiliar.esta_vacia():
                self._creadas.apilar(auxiliar.desapilar())
            return resultado

    def tamanios(self) -> tuple[int, int, int, int]:
        """Tamaño de la cola de pendientes, del registro, del historial y de la pila de deshacer. O(1)."""
        with self._candado:
            return (self._pendientes.tamanio(), self._registro.tamanio(), self._eventos.tamanio(),
                    self._creadas.tamanio())

    def estado_cartera(self, precio: float | None = None) -> EstadoCartera:
        """Cartera valorada al precio dado, o al precio actual (consultado fuera del candado)."""
        valor = self._fuente.obtener_precio_actual(self._simbolo) if precio is None else precio
        with self._candado:
            return self._cartera.estado(valor)

    def registrar_evento(self, tipo: TipoEvento, id_orden: int | None, descripcion: str) -> None:
        """Agrega un evento al historial (lo usa el bot para sus decisiones)."""
        with self._candado:
            self._apilar_evento(tipo, id_orden, descripcion)
            self._guardar()

    def _apilar_evento(self, tipo: TipoEvento, id_orden: int | None, descripcion: str) -> None:
        """Se llama con el candado tomado. O(1)."""
        self._eventos.apilar(Evento(self._reloj(), tipo, id_orden, descripcion))


def _de_abajo_hacia_arriba[T](pila: Pila[T]) -> Lista[T]:
    """Elementos de una pila del fondo al tope, sin perderla.

    Se desapila todo a una auxiliar (que queda con el fondo arriba) y al
    devolverlos salen del fondo al tope. Complejidad: O(n).
    """
    auxiliar: Pila[T] = Pila()
    while not pila.esta_vacia():
        auxiliar.apilar(pila.desapilar())
    resultado: Lista[T] = Lista()
    while not auxiliar.esta_vacia():
        elemento = auxiliar.desapilar()
        resultado.agregar(elemento)
        pila.apilar(elemento)
    return resultado
