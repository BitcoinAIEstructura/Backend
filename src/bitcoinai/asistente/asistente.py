"""El asistente del chat con el bot: entiende preguntas sencillas y responde con tus datos.

No usa servicios externos ni inteligencia artificial generativa: reconoce palabras
con un ``Trie`` de raíces y suma votos en una ``TablaHash``. Nunca ejecuta nada por su
cuenta: si la persona pide encender o detener el bot, responde con una *acción* que
el frontend muestra como botón, y solo al tocarlo se hace (la confirmación es de ella).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from bitcoinai.asistente import intenciones as i
from bitcoinai.busqueda.buscador import palabras
from bitcoinai.estrategia import Senal
from bitcoinai.estructuras import Lista, TablaHash, Trie
from bitcoinai.simulacion import EstadoBot, EstadoCartera

LARGO_MAXIMO = 300
PUNTAJE_MINIMO = 1.0

# Palabras que no ayudan a entender ("¿qué es el…?"): no votan.
PALABRAS_VACIAS = ("que el la los las un una unos unas de del es y o a al en mi me te tu se lo le por con "
                   "como eso esto esta este son hay he has ha ya muy mas sobre su sus mis tus nos para cual "
                   "cuales dime dame quiero puedo")

_SENAL_EN_PALABRAS = {Senal.COMPRAR: "comprar", Senal.VENDER: "vender", Senal.MANTENER: "esperar"}


@dataclass(frozen=True, slots=True)
class Voto:
    intencion: str
    peso: float


@dataclass(frozen=True, slots=True)
class Accion:
    """Algo que la persona puede hacer con un toque: encender o detener el bot, o ir a una página."""

    tipo: str  # "INICIAR_BOT", "DETENER_BOT" o "IR"
    etiqueta: str
    ruta: str | None = None


@dataclass(frozen=True, slots=True)
class Respuesta:
    intencion: str
    texto: str
    accion: Accion | None
    sugerencias: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DatosUsuario:
    """Lo que el asistente puede contar de la persona (la cartera es None si no hubo precio)."""

    cartera: EstadoCartera | None
    bot: EstadoBot
    pendientes: int


def usdt(valor: float) -> str:
    """Cifra a la colombiana: 1234.5 → "1.234,50"."""
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def decimal(valor: float, decimales: int = 2) -> str:
    """Con coma decimal: 0.5 → "0,50"."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def duracion(ms: float) -> str:
    """Cuánto tiempo, en palabras: "45 s", "3 min", "2 h 5 min"."""
    segundos = max(0, round(ms / 1000))
    if segundos < 60:
        return f"{segundos} s"
    minutos = segundos // 60
    if minutos < 60:
        return f"{minutos} min"
    horas, resto = divmod(minutos, 60)
    return f"{horas} h {resto} min" if resto else f"{horas} h"


def cada_cuanto(segundos: int) -> str:
    if segundos < 60:
        return f"cada {segundos} segundos"
    if segundos == 60:
        return "cada minuto"
    return f"cada {duracion(segundos * 1000)}"


def _preparar(mensaje: str) -> str:
    """Junta "por qué" en "porque" y entiende "para el bot" como una orden."""
    texto = " ".join(palabras(mensaje[:LARGO_MAXIMO]))
    texto = texto.replace("por que", "porque")
    if texto.startswith("para ") and "bot" in texto:
        texto = "parar" + texto[4:]
    return texto


class Asistente:
    """Reconoce la intención de un mensaje y arma la respuesta.

    - Cada raíz va al ``Trie`` con sus votos. Para cada palabra del mensaje se busca la
      raíz más larga que sea su comienzo ("encendido" → "encendido", no "encend"): así
      "¿está encendido?" pregunta por el estado y "enciende" pide encenderlo.
    - Los votos se suman en una ``TablaHash`` (intención → puntaje); gana el mayor.
    - Complejidad de entender un mensaje de p palabras de largo m: O(p·m²) en el peor caso
      (cada comienzo de palabra es una búsqueda O(m) en el trie).
    """

    def __init__(self, reloj: Callable[[], float] = lambda: time.time() * 1000) -> None:
        self._reloj = reloj
        self._trie: Trie[Lista[Voto]] = Trie()
        self._vacias: TablaHash[str, None] = TablaHash()
        self._conceptos: TablaHash[str, str] = TablaHash()
        self._sugerencias: TablaHash[str, tuple[str, ...]] = TablaHash()
        for palabra in PALABRAS_VACIAS.split():
            self._vacias.poner(palabra, None)
        for intencion in i.INTENCIONES:
            self._indexar(intencion.id, intencion.raices)
            self._sugerencias.poner(intencion.id, intencion.sugerencias)
        for concepto in i.GLOSARIO:
            clave = f"concepto:{concepto.id}"
            self._indexar(clave, concepto.raices)
            self._conceptos.poner(clave, concepto.explicacion)
        # El orden de los empates: el del catálogo.
        self._orden: TablaHash[str, int] = TablaHash()
        for posicion, ident in enumerate((*(x.id for x in i.INTENCIONES), *(f"concepto:{c.id}" for c in i.GLOSARIO))):
            self._orden.poner(ident, posicion)

    def _indexar(self, intencion: str, raices: str) -> None:
        for texto in raices.split():
            raiz, _, peso = texto.partition(":")
            votos = self._trie.buscar(raiz)
            if votos is None:
                votos = Lista()
                self._trie.insertar(raiz, votos)
            votos.agregar(Voto(intencion, float(peso) if peso else 1.0))

    def _votos_de(self, palabra: str) -> Lista[Voto] | None:
        """Los votos de la raíz más larga con la que empieza la palabra (las de 2 letras, exactas).

        Recorre los comienzos de menor a mayor y para en cuanto el trie ya no tiene ese prefijo.
        """
        votos: Lista[Voto] | None = None
        for largo in range(2, len(palabra) + 1):
            prefijo = palabra[:largo]
            if not self._trie.hay_prefijo(prefijo):
                break
            encontrados = self._trie.buscar(prefijo)
            if encontrados is not None and (largo > 2 or largo == len(palabra)):
                votos = encontrados
        return votos

    def entender(self, mensaje: str) -> str:
        """La intención del mensaje, o ``NO_ENTENDI``."""
        puntajes: TablaHash[str, float] = TablaHash()
        for palabra in _preparar(mensaje).split():
            if self._vacias.contiene(palabra):
                continue
            votos = self._votos_de(palabra)
            for voto in votos or ():
                puntajes.poner(voto.intencion, (puntajes.obtener(voto.intencion) or 0.0) + voto.peso)
        mejor, mejor_puntaje = i.NO_ENTENDI, PUNTAJE_MINIMO - 1e-9
        for intencion, puntaje in puntajes.elementos():
            empata_antes = puntaje == mejor_puntaje and (self._orden.obtener(intencion) or 0) < (
                self._orden.obtener(mejor) or 0)
            if puntaje > mejor_puntaje or empata_antes:
                mejor, mejor_puntaje = intencion, puntaje
        return mejor

    def responder(self, mensaje: str, datos: DatosUsuario) -> Respuesta:
        intencion = self.entender(mensaje)
        explicacion = self._conceptos.obtener(intencion)
        if explicacion is not None:
            return Respuesta(intencion, explicacion, None, ("¿Qué estás haciendo?", "¿Cuánto he ganado?"))
        texto, accion = self._armar(intencion, datos)
        sugerencias = self._sugerencias.obtener(intencion) or i.SUGERENCIAS_INICIALES
        return Respuesta(intencion, texto, accion, sugerencias)

    def _armar(self, intencion: str, d: DatosUsuario) -> tuple[str, Accion | None]:
        bot, c = d.bot, d.bot.configuracion
        if intencion == i.SALUDO:
            return ("¡Hola! Soy tu bot de práctica. Puedes preguntarme qué estoy haciendo, por qué decidí algo, "
                    "cuánto has ganado o qué significa una palabra."), None
        if intencion == i.GRACIAS:
            return "¡Con gusto! Aquí sigo si necesitas algo más.", None
        if intencion == i.AYUDA:
            return ("Puedo contarte qué estoy haciendo y por qué, cuánto has ganado, el precio del Bitcoin y "
                    "tus órdenes en espera. También explico palabras como «stop loss», «RSI» o «vela», y puedo "
                    "encenderme o detenerme si me lo pides (siempre te pido confirmar)."), None
        if intencion == i.ESTADO_BOT:
            return self._estado(bot), None if bot.activo else Accion("INICIAR_BOT", "Sí, enciéndete")
        if intencion == i.INICIAR_BOT:
            if bot.activo:
                return "Ya estoy encendido. " + self._estado(bot), None
            return (f"¿Me enciendo? Revisaré el mercado {cada_cuanto(c.segundos_entre_ciclos)} y usaré el "
                    f"{c.riesgo * 100:.0f} % de tus USDT en cada compra. Puedes cambiarlo en la página Bot."), \
                Accion("INICIAR_BOT", "Sí, enciéndete")
        if intencion == i.DETENER_BOT:
            if not bot.activo:
                return "Ya estoy detenido. No haré nada hasta que me enciendas.", None
            return ("¿Me detengo? Dejaré de comprar y vender. Lo que ya tienes se queda igual en tu cartera."), \
                Accion("DETENER_BOT", "Sí, detente")
        if intencion == i.POR_QUE:
            return self._por_que(bot), None
        if intencion == i.GANANCIA:
            return self._ganancia(d.cartera), Accion("IR", "Ver mi cartera", "/cartera")
        if intencion == i.PRECIO:
            if d.cartera is None:
                return "Ahora no pude leer el precio. Intenta de nuevo en un momento.", None
            return f"Ahora 1 Bitcoin cuesta {usdt(d.cartera.precio_actual)} USDT.", Accion(
                "IR", "Ver el mercado", "/mercado")
        if intencion == i.ORDENES:
            if d.pendientes == 0:
                texto = "No tienes órdenes esperando en la cola."
            else:
                cuantas = "1 orden espera" if d.pendientes == 1 else f"{d.pendientes} órdenes esperan"
                quien = "Yo las ejecuto al final de cada revisión." if bot.activo else \
                    "Puedes ejecutarlas en la página Órdenes o encenderme para que lo haga yo."
                texto = f"{cuantas} en la cola. {quien}"
            return texto, Accion("IR", "Ir a Órdenes", "/ordenes")
        if intencion == i.IA:
            return ("En la página Predicciones IA, cuatro modelos aprenden de las velas pasadas y dicen si creen "
                    "que la próxima subirá o bajará, con su porcentaje de acierto. Ojo: nadie adivina el "
                    "mercado; úsalo para aprender, no como garantía."), Accion("IR", "Ver Predicciones IA", "/ia")
        return ("No entendí bien. Puedo contarte qué estoy haciendo, por qué decidí algo, cuánto has ganado o "
                "explicarte palabras como «stop loss». Prueba con una de estas preguntas:"), None

    def _estado(self, bot: EstadoBot) -> str:
        c = bot.configuracion
        if not bot.activo:
            return (f"Estoy apagado. Si me enciendes, revisaré el mercado {cada_cuanto(c.segundos_entre_ciclos)} "
                    "y decidiré si comprar, vender o esperar.")
        ahora = self._reloj()
        partes = Lista[str]()
        if bot.encendido_desde is not None:
            partes.agregar(f"Estoy encendido desde hace {duracion(ahora - bot.encendido_desde)}.")
        else:
            partes.agregar("Estoy encendido.")
        revisiones = "1 vez" if bot.ciclos == 1 else f"{bot.ciclos} veces"
        partes.agregar(f"He revisado el mercado {revisiones}.")
        if bot.en_ciclo:
            partes.agregar("Justo ahora lo estoy revisando.")
        elif bot.ultimo_ciclo is not None:
            falta = bot.ultimo_ciclo + c.segundos_entre_ciclos * 1000 - ahora
            partes.agregar(f"La próxima revisión es en {duracion(falta)}." if falta > 0
                           else "La próxima revisión empieza en un momento.")
        if bot.ultima_decision is not None:
            partes.agregar(f"Lo último que decidí fue {_SENAL_EN_PALABRAS[bot.ultima_decision.senal]}.")
        if bot.ultimo_error:
            partes.agregar("La última revisión falló (seguramente no pude leer el mercado); lo vuelvo a intentar "
                           "en la próxima.")
        return " ".join(partes)

    @staticmethod
    def _por_que(bot: EstadoBot) -> str:
        d = bot.ultima_decision
        if d is None:
            return ("Todavía no he decidido nada. Cuando me enciendes, lo primero que hago es revisar el mercado "
                    "y te cuento qué decidí.")
        accion = _SENAL_EN_PALABRAS[d.senal]
        return (f"Decidí {accion} porque les pregunto a tres estrategias (cruce de medias, RSI y MACD) y la "
                f"opción «{accion}» sacó el {d.confianza * 100:.0f} % de los votos. El Bitcoin estaba en "
                f"{usdt(d.precio)} USDT. Detalle técnico: {d.motivo}")

    @staticmethod
    def _ganancia(c: EstadoCartera | None) -> str:
        if c is None:
            return "Ahora no pude leer el precio para valorar tu cartera. Intenta de nuevo en un momento."
        if abs(c.ganancia_total) < 0.005:
            resultado = "Por ahora vas igual: ni ganas ni pierdes."
        else:
            verbo = "ganando" if c.ganancia_total > 0 else "perdiendo"
            resultado = f"Vas {verbo} {usdt(abs(c.ganancia_total))} USDT ({decimal(abs(c.rentabilidad) * 100)} %)."
        btc = f" y {decimal(c.btc, 8)} BTC que valen {usdt(c.valor_btc)} USDT" if c.btc > 0 else ""
        return (f"Tienes {usdt(c.valor_total)} USDT en total; empezaste con {usdt(c.saldo_inicial)}. {resultado} "
                f"Ahora tienes {usdt(c.saldo_usdt)} USDT libres{btc}. Recuerda: es dinero simulado.")

