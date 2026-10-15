"""Bot de trading simulado. Nunca opera con dinero real."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from bitcoinai.estrategia import Decision, Estrategia, Senal
from bitcoinai.mercado import FuenteDeMercado, velas_cerradas
from bitcoinai.modelo import Intervalo
from bitcoinai.simulacion.cartera import EstadoCartera
from bitcoinai.simulacion.interfaces import PublicadorEventos, SinPublicar
from bitcoinai.simulacion.libro import LibroDeOrdenes
from bitcoinai.simulacion.modelo import OperacionInvalidaError, TipoEvento

COMPRA_MINIMA = 1.0
"""Compra mínima en USDT; con menos saldo el bot no compra."""

_MAXIMO_PROCESADAS_POR_CICLO = 100


@dataclass(frozen=True, slots=True)
class ConfiguracionBot:
    """Configuración del bot simulado.

    Atributos:
        segundos_entre_ciclos: cada cuántos segundos decide (1 a 86 400).
        intervalo: intervalo de las velas que analiza ("1m" … "1d").
        cantidad_velas: cuántas velas analiza (2 a 1000).
        riesgo: fracción del saldo que usa en cada compra (0,2 = 20 %).
        stop_loss: pérdida desde el costo promedio que dispara la venta (0,05 = 5 %).
        take_profit: ganancia desde el costo promedio que dispara la venta (0,10 = 10 %).
    """

    segundos_entre_ciclos: int = 60
    intervalo: str = "1h"
    cantidad_velas: int = 200
    riesgo: float = 0.20
    stop_loss: float = 0.05
    take_profit: float = 0.10

    def __post_init__(self) -> None:
        """Raises: ValueError con un mensaje claro si algún valor está fuera de rango."""
        if not 1 <= self.segundos_entre_ciclos <= 86_400:
            raise ValueError("'segundosEntreCiclos' debe estar entre 1 y 86400")
        Intervalo.desde_codigo(self.intervalo)  # ValueError con los valores permitidos
        if not 2 <= self.cantidad_velas <= 1000:
            raise ValueError("'cantidadVelas' debe estar entre 2 y 1000")
        if not 0 < self.riesgo <= 1:
            raise ValueError("'riesgo' debe ser mayor que 0 y como máximo 1")
        if not 0 < self.stop_loss < 1:
            raise ValueError("'stopLoss' debe estar entre 0 y 1, sin incluirlos")
        if not 0 < self.take_profit <= 10:
            raise ValueError("'takeProfit' debe ser mayor que 0 y como máximo 10")


@dataclass(frozen=True, slots=True)
class EstadoBot:
    """Estado del bot: si está activo, su configuración, ciclos y la última decisión o error.

    ``encendido_desde`` es cuándo se encendió (ms; None si está detenido) y ``en_ciclo``
    dice si en este momento está revisando el mercado: así se ve que trabaja.
    """

    activo: bool
    estrategia: str
    configuracion: ConfiguracionBot
    ciclos: int
    ultimo_ciclo: int | None
    ultima_decision: Decision | None
    ultimo_error: str | None
    encendido_desde: int | None = None
    en_ciclo: bool = False


class BotSimulado:
    """Bot de trading simulado.

    Cada ``segundos_entre_ciclos`` (en un hilo propio) ejecuta un ciclo:

    1. Pide las velas más recientes (solo las cerradas) y el precio actual.
    2. Consulta la estrategia (por defecto la combinada) y registra su decisión con
       el motivo en el historial.
    3. Si hay posición y el precio cayó ``stop_loss`` o más desde el costo promedio,
       vende todo (stop-loss); si subió ``take_profit`` o más, vende todo
       (take-profit). Esto tiene prioridad sobre la estrategia.
    4. Si no, con COMPRAR y sin posición, compra por ``riesgo`` × saldo; con VENDER
       y con posición, vende todo el BTC.
    5. Procesa las órdenes pendientes de la cola, en orden FIFO: el bot hace de
       motor de ejecución.

    Un ciclo que falla (por ejemplo, porque Binance no responde) se registra como
    error y el bot sigue con el próximo.

    Tiempo real: publica "senal" con la ``Decision`` solo cuando la señal cambia
    respecto del ciclo anterior (al iniciar, la primera siempre se publica).
    """

    def __init__(self, libro: LibroDeOrdenes, fuente: FuenteDeMercado, estrategia: Estrategia, simbolo: str,
                 reloj: Callable[[], int] = lambda: int(time.time() * 1000)) -> None:
        self._libro = libro
        self._fuente = fuente
        self._estrategia = estrategia
        self._simbolo = simbolo
        self._reloj = reloj
        self._candado = threading.Lock()  # iniciar / detener
        self._candado_ciclo = threading.Lock()  # un ciclo a la vez
        self._parar: threading.Event | None = None
        self._configuracion = ConfiguracionBot()
        self._ciclos = 0
        self._ultimo_ciclo: int | None = None
        self._ultima_decision: Decision | None = None
        self._ultimo_error: str | None = None
        self._encendido_desde: int | None = None
        self._en_ciclo = False
        self._publicador: PublicadorEventos = SinPublicar()
        self._ultima_senal_publicada: Senal | None = None

    def usar_publicador(self, publicador: PublicadorEventos) -> None:
        """A quién avisar cuando cambia la señal."""
        self._publicador = publicador

    def iniciar(self, configuracion: ConfiguracionBot) -> EstadoBot:
        """Pone en marcha el bot; el primer ciclo empieza enseguida.

        Raises:
            OperacionInvalidaError: si ya estaba en marcha.
        """
        with self._candado:
            if self._parar is not None:
                raise OperacionInvalidaError("El bot ya está en marcha; deténlo antes de iniciarlo de nuevo")
            self._configuracion = configuracion
            self._ultima_senal_publicada = None
            self._encendido_desde = self._reloj()
            parar = threading.Event()
            self._parar = parar
            hilo = threading.Thread(target=self._bucle, args=(parar, configuracion.segundos_entre_ciclos),
                                    name="bot-simulado", daemon=True)
            hilo.start()
            c = configuracion
            self._libro.registrar_evento(
                TipoEvento.BOT_INICIADO, None,
                f"Bot iniciado: estrategia {self._estrategia.nombre()}, cada {c.segundos_entre_ciclos} s, "
                f"velas de {c.intervalo}, riesgo {c.riesgo * 100:.0f} %, stop-loss {c.stop_loss * 100:.1f} %, "
                f"take-profit {c.take_profit * 100:.1f} %.")
            return self.estado()

    def detener(self) -> EstadoBot:
        """Detiene el bot (deja terminar el ciclo en curso). Si ya estaba detenido no hace nada."""
        with self._candado:
            if self._parar is not None:
                self._parar.set()
                self._parar = None
                self._encendido_desde = None
                self._libro.registrar_evento(TipoEvento.BOT_DETENIDO, None, "Bot detenido.")
            return self.estado()

    def estado(self) -> EstadoBot:
        """Estado actual del bot."""
        return EstadoBot(self._parar is not None, self._estrategia.nombre(), self._configuracion, self._ciclos,
                         self._ultimo_ciclo, self._ultima_decision, self._ultimo_error,
                         self._encendido_desde, self._en_ciclo)

    def _bucle(self, parar: threading.Event, segundos: int) -> None:
        # "Espera fija" entre ciclos: un ciclo nunca se superpone con el siguiente.
        while not parar.is_set():
            self.ejecutar_ciclo()
            parar.wait(segundos)

    def ejecutar_ciclo(self) -> None:
        """Ejecuta un ciclo completo ahora mismo (lo llama el hilo; también sirve en pruebas).

        Nunca lanza excepciones: los errores quedan en el estado y en el historial.
        """
        with self._candado_ciclo:
            config = self._configuracion
            self._en_ciclo = True
            try:
                velas = velas_cerradas(self._fuente.obtener_velas(
                    self._simbolo, Intervalo.desde_codigo(config.intervalo), config.cantidad_velas), self._reloj())
                precio = self._fuente.obtener_precio_actual(self._simbolo)
                cartera = self._libro.estado_cartera(precio)
                decision = self._estrategia.evaluar(velas)
                self._ultima_decision = decision
                if decision.senal is not self._ultima_senal_publicada:
                    self._ultima_senal_publicada = decision.senal
                    self._publicador.publicar("senal", decision)
                self._libro.registrar_evento(
                    TipoEvento.DECISION_BOT, None,
                    f"El bot decidió {decision.senal.name} (confianza {decision.confianza:.2f}): {decision.motivo}")
                hay_posicion = cartera.btc > 0
                if not (hay_posicion and self._revisar_salida_de_riesgo(cartera, precio, config)):
                    self._actuar_segun_decision(decision, cartera, hay_posicion, config)
                self._procesar_pendientes()
                self._ultimo_error = None
            except Exception as error:
                self._ultimo_error = str(error) or type(error).__name__
                self._libro.registrar_evento(TipoEvento.ERROR_BOT, None,
                                             f"El ciclo del bot falló: {self._ultimo_error}")
            finally:
                self._ciclos += 1
                self._ultimo_ciclo = self._reloj()
                self._en_ciclo = False

    def _revisar_salida_de_riesgo(self, cartera: EstadoCartera, precio: float, config: ConfiguracionBot) -> bool:
        """Stop-loss y take-profit. Devuelve True si creó una orden de venta."""
        costo = cartera.costo_promedio
        if costo <= 0:
            return False
        variacion = precio / costo - 1
        if variacion <= -config.stop_loss:
            tipo, nombre = TipoEvento.STOP_LOSS, "stop-loss"
        elif variacion >= config.take_profit:
            tipo, nombre = TipoEvento.TAKE_PROFIT, "take-profit"
        else:
            return False
        detalle = (f"{nombre}: el precio {precio:.2f} está {variacion * 100:+.2f} % "
                   f"respecto del costo promedio {costo:.2f}")
        orden = self._libro.crear_venta_total(detalle)
        self._libro.registrar_evento(tipo, orden.id, f"El bot vende todo por {detalle}.")
        return True

    def _actuar_segun_decision(self, decision: Decision, cartera: EstadoCartera, hay_posicion: bool,
                               config: ConfiguracionBot) -> None:
        if decision.senal is Senal.COMPRAR and not hay_posicion:
            monto = cartera.saldo_usdt * config.riesgo
            if monto >= COMPRA_MINIMA:
                self._libro.crear_compra(monto, f"señal del bot: {decision.motivo}")
        elif decision.senal is Senal.VENDER and hay_posicion:
            self._libro.crear_venta_total(f"señal del bot: {decision.motivo}")

    def _procesar_pendientes(self) -> None:
        for _ in range(_MAXIMO_PROCESADAS_POR_CICLO):
            if self._libro.procesar_siguiente() is None:
                return
