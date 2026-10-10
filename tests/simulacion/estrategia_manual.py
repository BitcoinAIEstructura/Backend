"""Estrategia falsa para las pruebas de la simulación: devuelve la señal que se le indique."""

from bitcoinai.estrategia import CONFIANZA_NEUTRA, Decision, Estrategia, Senal
from bitcoinai.estructuras import ListaDoble
from bitcoinai.modelo import Vela


class EstrategiaManual(Estrategia):
    def __init__(self) -> None:
        self.senal = Senal.MANTENER
        super().__init__()

    def decir(self, senal: Senal) -> None:
        self.senal = senal

    def nombre(self) -> str:
        return "manual"

    def parametros(self) -> dict[str, object]:
        return {}

    def velas_minimas(self) -> int:
        return 1

    def evaluar(self, velas_hasta_ahora: ListaDoble[Vela] | None) -> Decision:
        velas = velas_hasta_ahora
        tiempo = velas.ultimo().tiempo_apertura if velas is not None and not velas.esta_vacia() else 0
        precio = velas.ultimo().cierre if velas is not None and not velas.esta_vacia() else 0.0
        confianza = CONFIANZA_NEUTRA if self.senal is Senal.MANTENER else 0.9
        return Decision(tiempo, self.senal, precio, confianza, f"la prueba pidió {self.senal.name}")

    def _decidir(self, velas: ListaDoble[Vela]) -> Decision:
        return self.evaluar(velas)
