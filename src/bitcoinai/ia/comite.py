"""Comité: junta las probabilidades de varios modelos, pesando más al que mejor le fue."""

from collections.abc import Callable

from bitcoinai.estructuras import Lista
from bitcoinai.ia.base import Explicacion, Modelo, Vector, por_peso, porcentaje
from bitcoinai.ia.caracteristicas import Muestra
from bitcoinai.ia.evaluacion import dividir_en_el_tiempo, evaluar

PESO_MINIMO = 0.05
"""Ningún miembro queda con peso cero: un mal momento no lo saca del todo."""


class Comite:
    """Promedio ponderado de las probabilidades de sus miembros.

    Los pesos salen de una validación dentro del entrenamiento (nunca de la prueba
    final, que sería hacer trampa): se entrena a cada miembro con el primer 80 % del
    entrenamiento, se mide cuánto supera a la base en el 20 % siguiente, y luego se
    vuelve a entrenar con todo el entrenamiento. Peso = ventaja sobre la base, con
    un mínimo. Si ninguno supera la base, quedan todos iguales.
    """

    nombre = "Comité"

    def __init__(self, fabricas: tuple[Callable[[], Modelo], ...]) -> None:
        self._fabricas = fabricas
        self.miembros: tuple[Modelo, ...] = ()
        self.pesos: Vector = ()

    def entrenar(self, muestras: Lista[Muestra]) -> None:
        sub_entrenamiento, validacion = dividir_en_el_tiempo(muestras, 0.2)
        pesos: Vector = ()
        for fabrica in self._fabricas:
            prueba = fabrica()
            prueba.entrenar(sub_entrenamiento)
            pesos += (max(evaluar(prueba, validacion).ventaja, 0.0) + PESO_MINIMO,)
        total = sum(pesos)
        self.pesos = tuple(p / total for p in pesos)
        miembros: tuple[Modelo, ...] = ()
        for fabrica in self._fabricas:
            modelo = fabrica()
            modelo.entrenar(muestras)
            miembros += (modelo,)
        self.miembros = miembros

    def probabilidad(self, x: Vector) -> float:
        if not self.miembros:
            raise ValueError("El comité no está entrenado")
        return sum(p * m.probabilidad(x) for p, m in zip(self.pesos, self.miembros, strict=True))

    def explicar(self, x: Vector) -> Explicacion:
        votos = tuple((m.nombre, m.probabilidad(x), p) for m, p in zip(self.miembros, self.pesos, strict=True))
        pasos = tuple(f"{nombre}: {porcentaje(prob)} de que suba, con peso {porcentaje(peso)}."
                      for nombre, prob, peso in votos)
        # Cada miembro "empuja" según qué tan lejos de 50 % está y cuánto pesa.
        factores = por_peso((nombre, (prob - 0.5) * peso) for nombre, prob, peso in votos)
        a_favor = sum(1 for _, prob, _ in votos if prob >= 0.5)
        # "Empuja" y no "pesa": con pesos iguales, igual hay uno que mueve más el resultado.
        nombre, empuje = factores[0]
        hacia = "subir" if empuje >= 0 else "bajar"
        resumen = f"{a_favor} de {len(votos)} modelos creen que sube; el que más empuja es {nombre}, hacia {hacia}."
        return Explicacion(resumen=resumen, factores=factores, pasos=pasos)
