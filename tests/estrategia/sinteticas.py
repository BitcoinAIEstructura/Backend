"""Series de velas sintéticas y estrategias falsas para las pruebas de estrategias."""

from bitcoinai.estrategia import CONFIANZA_NEUTRA, Decision, Estrategia, Senal
from bitcoinai.estructuras import Lista, ListaDoble
from bitcoinai.modelo import Vela

DIA = 86_400_000
GIRO = 59
"""Índice de la vela donde cambia la tendencia en las series en V."""


def velas(aperturas: tuple[float, ...], cierres: tuple[float, ...]) -> ListaDoble[Vela]:
    """Velas con apertura y cierre dados (máximo y mínimo los envuelven), una por día desde t = 0."""
    resultado: ListaDoble[Vela] = ListaDoble()
    for i, (a, c) in enumerate(zip(aperturas, cierres, strict=True)):
        resultado.agregar_final(Vela(i * DIA, a, max(a, c), min(a, c), c, 1, i * DIA + DIA - 1))
    return resultado


def de_cierres(*cierres: float) -> ListaDoble[Vela]:
    """Velas planas (apertura = cierre)."""
    return velas(cierres, cierres)


def alcista_tras_caida() -> ListaDoble[Vela]:
    """Baja de 200 a 141 (vela 59) y luego sube 1,5 por vela. Forma de V."""
    return de_cierres(*(200 - i if i <= GIRO else 141 + 1.5 * (i - GIRO) for i in range(120)))


def bajista_tras_subida() -> ListaDoble[Vela]:
    """Sube de 100 a 159 (vela 59) y luego baja 1,5 por vela."""
    return de_cierres(*(100 + i if i <= GIRO else 159 - 1.5 * (i - GIRO) for i in range(120)))


def lateral_plano() -> ListaDoble[Vela]:
    return de_cierres(*(100.0 for _ in range(120)))


def lateral_zigzag() -> ListaDoble[Vela]:
    return de_cierres(*(100.0 if i % 2 == 0 else 101.0 for i in range(120)))


def primeras(todas: ListaDoble[Vela], n: int) -> ListaDoble[Vela]:
    copia: ListaDoble[Vela] = ListaDoble()
    for vela in todas:
        if copia.tamanio() == n:
            break
        copia.agregar_final(vela)
    return copia


def senales(estrategia: Estrategia, todas: ListaDoble[Vela]) -> tuple[str, ...]:
    """Evalúa en cada prefijo (como el backtest, con la lista creciendo) y devuelve
    las señales distintas de MANTENER como "COMPRAR@63"."""
    resultado: tuple[str, ...] = ()
    hasta_ahora: ListaDoble[Vela] = ListaDoble()
    for indice, vela in enumerate(todas):
        hasta_ahora.agregar_final(vela)
        decision = estrategia.evaluar(hasta_ahora)
        if decision.senal is not Senal.MANTENER:
            resultado += (f"{decision.senal.name}@{indice}",)
    return resultado


def indice_de(senal: str) -> int:
    return int(senal.split("@")[1])


class EstrategiaGuion(Estrategia):
    """Estrategia falsa: da la señal indicada en cada índice de vela (o una fija en todas)
    y registra lo que vio en cada llamada, para comprobar que nunca recibe velas del futuro."""

    def __init__(self, nombre: str = "guion", por_defecto: Senal = Senal.MANTENER, confianza: float = 1.0) -> None:
        self._nombre = nombre
        self._por_defecto = por_defecto
        self._confianza = confianza
        self._guion: dict[int, Senal] = {}
        self.tamanios_vistos: Lista[int] = Lista()
        self.tiempos_vistos: Lista[int] = Lista()
        super().__init__()

    def en(self, indice: int, senal: Senal) -> "EstrategiaGuion":
        self._guion[indice] = senal
        return self

    def nombre(self) -> str:
        return self._nombre

    def parametros(self) -> dict[str, object]:
        return {"nombre": self._nombre}

    def velas_minimas(self) -> int:
        return 1

    def evaluar(self, velas_hasta_ahora: ListaDoble[Vela] | None) -> Decision:
        assert velas_hasta_ahora is not None
        return self._decidir(velas_hasta_ahora)

    def _decidir(self, velas: ListaDoble[Vela]) -> Decision:
        self.tamanios_vistos.agregar(velas.tamanio())
        self.tiempos_vistos.agregar(velas.ultimo().tiempo_apertura)
        senal = self._guion.get(velas.tamanio() - 1, self._por_defecto)
        confianza = CONFIANZA_NEUTRA if senal is Senal.MANTENER else self._confianza
        return Decision(velas.ultimo().tiempo_apertura, senal, velas.ultimo().cierre, confianza,
                        f"{self._nombre} dice {senal.name} en la vela {velas.tamanio() - 1}.")

    def _valores_actuales(self) -> dict[str, float]:
        return {self._nombre: 1.0}
