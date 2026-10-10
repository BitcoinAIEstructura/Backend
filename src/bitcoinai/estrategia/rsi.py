"""Estrategia de reversión con el RSI."""

from bitcoinai.estrategia import apoyo
from bitcoinai.estrategia.apoyo import num
from bitcoinai.estrategia.base import Estrategia
from bitcoinai.estrategia.modelo import Decision, Senal
from bitcoinai.estructuras import ListaDoble
from bitcoinai.indicadores.incremental import RsiIncremental
from bitcoinai.modelo import Vela


class EstrategiaRsi(Estrategia):
    """Reversión con el RSI.

    - COMPRAR cuando el RSI estuvo por debajo de la sobreventa (30) y vuelve a subir por encima.
    - VENDER cuando estuvo por encima de la sobrecompra (70) y vuelve a bajar.
    - MANTENER en el resto.

    Se espera el giro en vez de comprar apenas entra en sobreventa, porque una
    caída fuerte puede seguir cayendo. La confianza crece con lo extremo que llegó
    a estar el RSI. Memoria incremental: O(1) por vela nueva.
    """

    def __init__(self, periodo: int = 14, sobreventa: float = 30, sobrecompra: float = 70) -> None:
        """Raises: ValueError si el periodo es menor que 1 o no se cumple 0 < sobreventa < 50 < sobrecompra < 100."""
        if periodo < 1:
            raise ValueError("El periodo del RSI debe ser al menos 1")
        if not (0 < sobreventa < 50 < sobrecompra < 100):
            raise ValueError("Se necesita 0 < sobreventa < 50 < sobrecompra < 100")
        self.periodo = periodo
        self.sobreventa = float(sobreventa)
        self.sobrecompra = float(sobrecompra)
        super().__init__()

    def nombre(self) -> str:
        return "rsi"

    def parametros(self) -> dict[str, object]:
        return {"periodo": self.periodo, "sobreventa": self.sobreventa, "sobrecompra": self.sobrecompra}

    def velas_minimas(self) -> int:
        """El RSI da su primer punto con periodo + 1 velas, y hacen falta dos puntos."""
        return self.periodo + 2

    def _reiniciar(self) -> None:
        self._rsi = RsiIncremental(self.periodo)
        self._antes: float | None = None
        self._ahora: float | None = None

    def _agregar(self, vela: Vela) -> None:
        valor = self._rsi.agregar(vela.cierre)
        if valor is not None:
            self._antes, self._ahora = self._ahora, valor

    def _decidir(self, velas: ListaDoble[Vela]) -> Decision:
        assert self._antes is not None and self._ahora is not None
        antes, ahora = self._antes, self._ahora
        if antes < self.sobreventa <= ahora:
            confianza = 0.6 + min(0.4, (self.sobreventa - antes) / self.sobreventa)
            return apoyo.decidir(velas, Senal.COMPRAR, confianza,
                                 f"El RSI salió de sobreventa: pasó de {num(antes)} a {num(ahora)} "
                                 f"cruzando {num(self.sobreventa)}; posible rebote al alza.")
        if antes > self.sobrecompra >= ahora:
            confianza = 0.6 + min(0.4, (antes - self.sobrecompra) / (100 - self.sobrecompra))
            return apoyo.decidir(velas, Senal.VENDER, confianza,
                                 f"El RSI salió de sobrecompra: pasó de {num(antes)} a {num(ahora)} "
                                 f"cruzando {num(self.sobrecompra)}; posible corrección a la baja.")
        if ahora < self.sobreventa:
            zona = f"está en sobreventa; se espera que vuelva a subir de {num(self.sobreventa)} para comprar"
        elif ahora > self.sobrecompra:
            zona = f"está en sobrecompra; se espera que vuelva a bajar de {num(self.sobrecompra)} para vender"
        else:
            zona = "está en zona neutral, sin señal de giro"
        return apoyo.decidir(velas, Senal.MANTENER, apoyo.CONFIANZA_NEUTRA, f"El RSI ({num(ahora)}) {zona}.")

    def _valores_actuales(self) -> dict[str, float]:
        return {} if self._rsi.valor is None else {"rsi": self._rsi.valor}
