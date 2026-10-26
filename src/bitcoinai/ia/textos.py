"""Lo que la página de predicciones dice en palabras: sale del backend, el frontend solo lo muestra.

Así la explicación de cada modelo y el veredicto ("le ganó o no a la base") se deciden en un
solo lugar, junto a los números que explican.
"""

from dataclasses import dataclass

from bitcoinai.ia.evaluacion import Metricas

ENCABEZADO = {
    "etiqueta": "Hecho a mano",
    "texto": ("Regresión logística, árbol de decisión y k vecinos, programados sin librerías de aprendizaje, más "
              "un comité que los combina. Aprenden del precio y de tres fuentes externas (el ánimo del mercado, "
              "los futuros de Binance y las opciones de Deribit). Todos responden lo mismo: ¿la próxima vela "
              "cerrará más arriba?"),
}

INTERVALOS: tuple[tuple[str, str], ...] = (("15m", "15 min"), ("1h", "1 h"), ("4h", "4 h"), ("1d", "1 día"))
"""(código, nombre para mostrar) de las velas que se pueden analizar."""


def nombre_intervalo(codigo: str) -> str:
    return next((nombre for c, nombre in INTERVALOS if c == codigo), codigo)


@dataclass(frozen=True, slots=True)
class DescripcionModelo:
    idea: str
    titulo_factores: str
    factores_con_signo: bool
    """True: el factor empuja a subir (+) o a bajar (−). False: es cuánto lo usa (un porcentaje)."""


DESCRIPCIONES: dict[str, DescripcionModelo] = {
    "Regresión logística": DescripcionModelo(
        "Suma las características con un peso cada una y lo convierte en probabilidad.",
        "Cuánto empuja cada característica", True),
    "Árbol de decisión": DescripcionModelo(
        "Hace preguntas sí/no sobre las características hasta llegar a una hoja.",
        "Qué características usa más el árbol", False),
    "k vecinos": DescripcionModelo(
        "Busca las 15 velas del pasado más parecidas y mira qué pasó después.",
        "Qué hace distinta a la vela de ahora", True),
    "Comité": DescripcionModelo(
        "Junta a los tres modelos y le da más peso al que mejor predijo en una prueba interna.",
        "Cuánto empuja cada modelo", True),
}


def descripcion(nombre: str) -> DescripcionModelo:
    return DESCRIPCIONES.get(nombre, DescripcionModelo("", "Factores", True))


def porcentaje(fraccion: float) -> str:
    """0,5263 → "52,6 %"."""
    return f"{fraccion * 100:.1f} %".replace(".", ",")


def puntos(diferencia: float) -> str:
    """0,021 → "+2,1 puntos"."""
    signo = "+" if diferencia >= 0 else "−"
    return f"{signo}{abs(diferencia) * 100:.1f} puntos".replace(".", ",")


@dataclass(frozen=True, slots=True)
class Veredicto:
    gana: bool
    titulo: str
    texto: str


def veredicto(m: Metricas) -> Veredicto:
    """Lo honesto: si en la prueba no le ganó a "decir siempre lo que más pasó", se dice claro."""
    if m.ventaja > 0:
        return Veredicto(True, "✓ Le ganó a la base.",
                         f"En las últimas {m.muestras} velas (que no vio al aprender) acertó el "
                         f"{porcentaje(m.exactitud)}, frente al {porcentaje(m.base)} de decir siempre lo que más "
                         f"pasó: {puntos(m.ventaja)} a favor.")
    return Veredicto(False, "⚠ Ojo: no le ganó a la base.",
                     f"En las últimas {m.muestras} velas acertó el {porcentaje(m.exactitud)}, y decir siempre lo "
                     f"que más pasó habría acertado el {porcentaje(m.base)}. Tómalo como un experimento, no como "
                     "una señal para operar.")


def conclusion_externos(sin: Metricas, con: Metricas) -> str:
    """Si las fuentes externas ayudaron, en una frase (comparando el mismo modelo con y sin ellas)."""
    diferencia = con.exactitud - sin.exactitud
    if abs(diferencia) < 0.005:
        return (f"Con y sin las fuentes externas acertó casi lo mismo ({porcentaje(con.exactitud)} frente a "
                f"{porcentaje(sin.exactitud)}): en este periodo no cambiaron mucho las cosas.")
    if diferencia > 0:
        return (f"Con las fuentes externas acertó más: {porcentaje(con.exactitud)} frente a "
                f"{porcentaje(sin.exactitud)} solo con el precio ({puntos(diferencia)}).")
    return (f"Con las fuentes externas acertó menos: {porcentaje(con.exactitud)} frente a "
            f"{porcentaje(sin.exactitud)} solo con el precio ({puntos(diferencia)}). Más datos no siempre "
            "ayudan: a veces solo agregan ruido.")
