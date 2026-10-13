"""Alertas de cada usuario: se guardan en la base y un vigilante revisa el precio."""

import logging
import threading
import time
from collections.abc import Callable

from bitcoinai.alertas.tablero import Alerta, EstadoAlerta, TableroAlertas, TipoAlerta
from bitcoinai.basedatos import BaseDatos, Fila
from bitcoinai.estructuras import Lista
from bitcoinai.mercado import FuenteDeMercado

MAXIMO_POR_USUARIO = 20
PRECIO_MAXIMO = 10_000_000
PERIODO_S = 10.0

LOG = logging.getLogger("bitcoinai.alertas")


class AlertaInvalidaError(ValueError):
    """Los datos de la alerta no sirven (el mensaje dice por qué)."""


class AlertaNoEncontradaError(LookupError):
    """No existe una alerta activa con ese id para ese usuario."""


def _ahora_ms() -> int:
    return int(time.time() * 1000)


def _alerta(f: Fila) -> Alerta:
    return Alerta(int(f["id"]), int(f["usuario_id"]), TipoAlerta(f["tipo"]), float(f["precio"]),
                  EstadoAlerta(f["estado"]), int(f["creada_en"]), f["disparada_en"], f["precio_disparo"])


class ServicioAlertas:
    """Crear, listar y cancelar alertas, y dispararlas cuando el precio llega.

    Las activas viven en un ``TableroAlertas`` (dos montículos) y en la tabla
    ``alertas``. Al disparar, se marca en la base y se avisa con ``al_disparar``
    (el tiempo real se lo manda solo a su dueño).
    """

    def __init__(self, bd: BaseDatos, fuente: FuenteDeMercado, simbolo: str,
                 al_disparar: Callable[[Alerta], None] = lambda _a: None,
                 reloj_ms: Callable[[], int] = _ahora_ms, periodo_s: float = PERIODO_S) -> None:
        self._bd = bd
        self._fuente = fuente
        self._simbolo = simbolo
        self._al_disparar = al_disparar
        self._reloj = reloj_ms
        self._periodo = periodo_s
        self._tablero = TableroAlertas()
        self._candado = threading.Lock()
        self._parar: threading.Event | None = None
        for f in bd.todas("SELECT * FROM alertas WHERE estado = 'ACTIVA'"):
            self._tablero.agregar(_alerta(f))

    def crear(self, usuario_id: int, tipo: str, precio: float, precio_actual: float) -> Alerta:
        """Raises: AlertaInvalidaError."""
        try:
            elegido = TipoAlerta(tipo.strip().upper())
        except ValueError:
            raise AlertaInvalidaError(f"Campo 'tipo' inválido: '{tipo}'. Valores permitidos: SUBE_A, BAJA_A") from None
        if not 0 < precio <= PRECIO_MAXIMO:
            raise AlertaInvalidaError(f"El precio debe ser mayor que 0 y como máximo {PRECIO_MAXIMO}")
        if elegido is TipoAlerta.SUBE_A and precio <= precio_actual:
            raise AlertaInvalidaError("Para avisar cuando suba, el precio debe estar por encima del actual")
        if elegido is TipoAlerta.BAJA_A and precio >= precio_actual:
            raise AlertaInvalidaError("Para avisar cuando baje, el precio debe estar por debajo del actual")
        with self._candado:
            if self._tablero.activas_de(usuario_id) >= MAXIMO_POR_USUARIO:
                raise AlertaInvalidaError(f"Ya tienes {MAXIMO_POR_USUARIO} alertas activas; cancela alguna")
            ahora = self._reloj()
            id_alerta = self._bd.ejecutar(
                "INSERT INTO alertas (usuario_id, tipo, precio, estado, creada_en) VALUES (?, ?, ?, 'ACTIVA', ?)",
                (usuario_id, elegido.value, precio, ahora))
            alerta = Alerta(id_alerta, usuario_id, elegido, precio, EstadoAlerta.ACTIVA, ahora)
            self._tablero.agregar(alerta)
            return alerta

    def listar(self, usuario_id: int, limite: int = 50) -> Lista[Alerta]:
        """Las del usuario, de la más nueva a la más vieja."""
        alertas: Lista[Alerta] = Lista()
        for f in self._bd.todas("SELECT * FROM alertas WHERE usuario_id = ? ORDER BY creada_en DESC, id DESC LIMIT ?",
                                (usuario_id, limite)):
            alertas.agregar(_alerta(f))
        return alertas

    def cancelar(self, usuario_id: int, id_alerta: int) -> None:
        """Raises: AlertaNoEncontradaError (también si es de otro usuario o ya no está activa)."""
        with self._candado:
            cambiadas = self._bd.contar_cambios(
                "UPDATE alertas SET estado = 'CANCELADA' WHERE id = ? AND usuario_id = ? AND estado = 'ACTIVA'",
                (id_alerta, usuario_id))
            if not cambiadas:
                raise AlertaNoEncontradaError(f"No tienes una alerta activa #{id_alerta}")
            self._tablero.cancelar(id_alerta)

    def revisar(self, precio: float) -> Lista[Alerta]:
        """Dispara las que se cumplen con este precio, las guarda y avisa. O(k log n)."""
        with self._candado:
            disparadas = self._tablero.revisar(precio, self._reloj())
            for a in disparadas:
                self._bd.ejecutar("UPDATE alertas SET estado = 'DISPARADA', disparada_en = ?, precio_disparo = ?"
                                  " WHERE id = ?", (a.disparada_en, a.precio_disparo, a.id))
        for a in disparadas:
            self._al_disparar(a)
        return disparadas

    def activas(self) -> int:
        with self._candado:
            return self._tablero.tamanio()

    # ---------- vigilante ----------

    def iniciar(self) -> None:
        """Cada ``periodo_s`` segundos, si hay alertas activas, consulta el precio y las revisa."""
        if self._parar is not None:
            return
        parar = threading.Event()
        self._parar = parar
        threading.Thread(target=self._vigilar, args=(parar,), name="vigilante-alertas", daemon=True).start()

    def detener(self) -> None:
        if self._parar is not None:
            self._parar.set()
            self._parar = None

    def _vigilar(self, parar: threading.Event) -> None:
        while not parar.wait(self._periodo):
            if self.activas() == 0:
                continue
            try:
                self.revisar(self._fuente.obtener_precio_actual(self._simbolo))
            except Exception as error:  # Binance caído: se intenta en la próxima vuelta
                LOG.debug("No se pudieron revisar las alertas: %s", error)
