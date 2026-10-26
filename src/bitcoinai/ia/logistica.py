"""Regresión logística entrenada con descenso por gradiente (sin librerías de aprendizaje)."""

from bitcoinai.estructuras import Lista
from bitcoinai.ia.base import Escalador, Explicacion, Vector, por_peso, sigmoide
from bitcoinai.ia.caracteristicas import NOMBRES, Muestra


class RegresionLogistica:
    """P(sube) = sigmoide(b + w·x), con x escalado.

    Entrenamiento: descenso por gradiente sobre el error logarítmico (log loss) con
    regularización L2, que castiga pesos grandes para no memorizar el ruido del
    mercado. Cada época recorre todas las muestras: O(épocas · n · d).

    Explicación: el aporte de cada característica es ``wⱼ · xⱼ``. Positivo empuja a
    "sube", negativo a "baja"; se muestran del que más pesa al que menos.
    """

    nombre = "Regresión logística"

    def __init__(self, tasa: float = 0.1, epocas: int = 300, l2: float = 0.01,
                 nombres: tuple[str, ...] = NOMBRES) -> None:
        self.tasa, self.epocas, self.l2 = tasa, epocas, l2
        self.nombres = nombres
        self.escalador = Escalador()
        self.pesos: Vector = ()
        self.sesgo = 0.0

    def entrenar(self, muestras: Lista[Muestra]) -> None:
        self.escalador.ajustar(muestras)
        datos: Lista[tuple[Vector, int]] = Lista()
        for m in muestras:
            datos.agregar((self.escalador.transformar(m.caracteristicas), m.etiqueta))
        n = datos.tamanio()
        d = len(self.nombres) if not n else len(datos.obtener(0)[0])
        pesos: Vector = (0.0,) * d
        sesgo = 0.0
        for _ in range(self.epocas):
            gradiente: Vector = (0.0,) * d
            gradiente_sesgo = 0.0
            for x, y in datos:
                error = sigmoide(sesgo + sum(w * v for w, v in zip(pesos, x, strict=True))) - y
                gradiente = tuple(g + error * v for g, v in zip(gradiente, x, strict=True))
                gradiente_sesgo += error
            pesos = tuple(w - self.tasa * (g / n + self.l2 * w) for w, g in zip(pesos, gradiente, strict=True))
            sesgo -= self.tasa * gradiente_sesgo / n
        self.pesos, self.sesgo = pesos, sesgo

    def _aportes(self, x: Vector) -> Vector:
        escalado = self.escalador.transformar(x)
        return tuple(w * v for w, v in zip(self.pesos, escalado, strict=True))

    def probabilidad(self, x: Vector) -> float:
        return sigmoide(self.sesgo + sum(self._aportes(x)))

    def explicar(self, x: Vector) -> Explicacion:
        factores = por_peso(zip(self.nombres, self._aportes(x), strict=True))
        principal, peso = factores[0]
        pasos = tuple(f"{nombre}: empuja a {'subir' if p > 0 else 'bajar'} ({p:+.2f})" for nombre, p in factores[:4])
        return Explicacion(
            resumen=f"Lo que más pesa es «{principal}», que empuja a {'subir' if peso > 0 else 'bajar'}.",
            factores=factores,
            pasos=pasos,
        )
