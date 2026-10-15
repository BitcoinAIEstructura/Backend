"""Lo que el asistente sabe reconocer: cada intención con sus raíces de palabras.

Una raíz es el comienzo de una palabra: "inici" reconoce "inicia", "iniciar" e
"inicializa". Cada raíz vota por su intención con un peso; gana la que más suma.
Las raíces van sin tildes y en minúsculas (como quedan al normalizar el mensaje).
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Intencion:
    id: str
    raices: str
    """Raíces separadas por espacios; ``raiz:peso`` cambia el peso (por defecto 1)."""
    sugerencias: tuple[str, ...] = ()


INICIAR_BOT = "iniciar-bot"
DETENER_BOT = "detener-bot"
ESTADO_BOT = "estado-bot"
POR_QUE = "por-que"
GANANCIA = "ganancia"
PRECIO = "precio"
ORDENES = "ordenes"
IA = "ia"
AYUDA = "ayuda"
SALUDO = "saludo"
GRACIAS = "gracias"
NO_ENTENDI = "no-entendi"

SUGERENCIAS_INICIALES = ("¿Qué estás haciendo?", "¿Cuánto he ganado?", "¿Qué es el stop loss?")

# El orden importa en los empates: gana la que aparece primero.
INTENCIONES: tuple[Intencion, ...] = (
    Intencion(INICIAR_BOT, "inici:2 enciend:2 encend:2 encender:2 arranc:2 prend:2 activa:2 empez:2 empiez:2 "
              "comienz:2 comenz:2 enciende:2", ("¿Qué estás haciendo?", "Detente")),
    Intencion(DETENER_BOT, "deten:2 detien:2 detener:2 apag:2 fren:2 parar:2 paral:2 pausa:2 "
              "quieto:2 basta:2", ("¿Qué estás haciendo?", "Enciéndete")),
    Intencion(ESTADO_BOT, "estado:2 estas:0.5 haciendo:2 haces:2 trabaj:2 funcion:1.5 activo:2 encendido:2 "
              "apagado:2 prendido:2 ciclo:1.5 revis:1.5 trabad:2 colgad:2 bot:0.5 robot:0.5",
              ("¿Por qué decidiste eso?", "¿Cuánto he ganado?")),
    Intencion(POR_QUE, "porque:2 razon:2 motivo:2 decision:2 decid:2 explica:1.5 compraste:2 "
              "vendiste:2 esperaste:2 senal:1.5", ("¿Qué es el RSI?", "¿Qué dice la IA?")),
    Intencion(GANANCIA, "gan:2 gane:2 perd:2 perdi:2 rendimiento:2 rentab:2 cartera:2 saldo:2 dinero:1.5 "
              "plata:1.5 tengo:1 cuanto:0.5 balance:2 voy:0.5 vas:0.5",
              ("¿Cuánto cuesta el Bitcoin?", "¿Qué estás haciendo?")),
    Intencion(PRECIO, "precio:2 vale:1.5 cuesta:2 cotiza:2 bitcoin:0.5 btc:0.5",
              ("¿Cuánto he ganado?", "¿Qué dice la IA?")),
    Intencion(ORDENES, "orden:2 pendiente:2 cola:2 espera:1", ("¿Cuánto he ganado?", "¿Qué es la comisión?")),
    Intencion(IA, "prediccion:2 predic:2 ia:2 intelig:2 modelo:1.5 comite:2 futuro:2 subira:2 bajara:2 "
              "pronost:2", ("¿Qué estás haciendo?", "¿Qué es una vela?")),
    Intencion(AYUDA, "ayuda:2 ayudame:2 puedes:1.5 sabes:1.5 sirves:2 comandos:2 opciones:2 hacer:0.5",
              SUGERENCIAS_INICIALES),
    Intencion(SALUDO, "hola:2 buenas:2 buenos:2 hey:2 saludos:2 holi:2", SUGERENCIAS_INICIALES),
    Intencion(GRACIAS, "gracias:2 genial:1.5 perfecto:1.5 listo:1 chevere:1.5 excelente:1.5",
              SUGERENCIAS_INICIALES),
)


@dataclass(frozen=True, slots=True)
class Concepto:
    id: str
    raices: str
    explicacion: str


# El glosario: palabras que asustan al principio, en lenguaje sencillo.
GLOSARIO: tuple[Concepto, ...] = (
    Concepto("stop-loss", "stop:1.5 loss:1.5 stoploss:3",
             "El stop loss es un freno de emergencia: si el Bitcoin cae cierto porcentaje desde lo que "
             "pagaste, vendo todo para que la pérdida no siga creciendo. Lo eliges en la pantalla del bot."),
    Concepto("take-profit", "take:1.5 profit:1.5 takeprofit:3",
             "El take profit es la meta de ganancia: si el Bitcoin sube cierto porcentaje desde lo que "
             "pagaste, vendo todo y guardo esa ganancia."),
    Concepto("riesgo", "riesgo:2",
             "El riesgo por compra es qué parte de tus USDT uso cada vez que compro. Con 20 %, si tienes "
             "1.000 USDT, compro por 200 y guardo el resto."),
    Concepto("usdt", "usdt:2 tether:2 dolar:1.5 dolares:1.5",
             "USDT es una moneda digital que vale casi lo mismo que un dólar. Aquí es tu dinero de "
             "práctica: empiezas con 10.000 USDT simulados."),
    Concepto("vela", "vela:2 velas:2 intervalo:1.5",
             "Una vela resume el precio en un rato (por ejemplo, 1 hora): dónde empezó, dónde terminó y "
             "hasta dónde subió y bajó. Verde si terminó más arriba; roja si terminó más abajo."),
    Concepto("rsi", "rsi:3",
             "El RSI es un medidor de 0 a 100 que dice si el precio subió o bajó demasiado rápido. Por "
             "encima de 70 suele estar «caro» y por debajo de 30, «barato»."),
    Concepto("macd", "macd:3",
             "El MACD compara dos promedios del precio para ver si toma fuerza hacia arriba o hacia abajo. "
             "Cuando su línea cruza hacia arriba, es una pista de compra."),
    Concepto("medias", "media:1.5 medias:1.5 cruce:1.5 movil:1.5",
             "Una media móvil es el promedio de los últimos precios. Cuando la media corta cruza por encima "
             "de la larga, el precio está tomando impulso hacia arriba."),
    Concepto("comision", "comision:2 comisiones:2",
             "Cada compra y cada venta paga una comisión del 0,1 %, como en un exchange real. Por 1.000 USDT "
             "son 1 USDT."),
    Concepto("simulado", "real:2.5 simul:2 practica:1.5 ficticio:2 riesgos:1",
             "Todo en Nexabit es simulado: el dinero es de práctica, nunca se usa dinero real y no se conecta "
             "a ninguna cuenta de un exchange. Puedes equivocarte sin perder nada."),
    Concepto("liga", "liga:2 ranking:2 puesto:1.5",
             "La liga ordena a los inversores por rentabilidad (cuánto ganaron respecto a lo que empezaron). "
             "Los nombres salen con alias para cuidar la privacidad."),
    Concepto("alerta", "alerta:2 alertas:2 avisa:1.5 avisame:1.5",
             "Una alerta te avisa cuando el Bitcoin llega a un precio. Se crean en la página Mercado."),
)
