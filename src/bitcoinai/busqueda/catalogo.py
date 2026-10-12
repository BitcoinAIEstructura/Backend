"""Lo que se puede encontrar con la búsqueda (Ctrl + K): páginas, acciones, indicadores y conceptos.

Las rutas son las del frontend. Las palabras clave suman sinónimos que no están en
el título ("2fa" lleva a la verificación en dos pasos).
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Entrada:
    id: str
    titulo: str
    descripcion: str
    ruta: str
    tipo: str  # "pagina", "accion", "indicador" o "concepto"
    claves: str = ""


CATALOGO: tuple[Entrada, ...] = (
    # ---------- páginas ----------
    Entrada("panel", "Panel", "Tu cartera, el precio en vivo y la señal de la IA", "/panel", "pagina",
            "inicio resumen"),
    Entrada("mercado", "Mercado", "Velas de BTCUSDT con indicadores técnicos", "/mercado", "pagina",
            "grafica precio velas"),
    Entrada("ordenes", "Órdenes", "Comprar, vender y la cola de pendientes", "/ordenes", "pagina", "operar"),
    Entrada("cartera", "Cartera", "Tu posición, ganancias e historial", "/cartera", "pagina", "saldo historial"),
    Entrada("bot", "Bot", "El bot que opera solo con la estrategia combinada", "/bot", "pagina", "automatico robot"),
    Entrada("liga", "Liga de inversores", "Los 10 mejores por rentabilidad y tu puesto", "/liga", "pagina",
            "ranking clasificacion top"),
    Entrada("si-hubiera", "¿Y si hubiera invertido?", "Cuánto valdría hoy una compra del pasado", "/liga#si-hubiera",
            "pagina", "maquina tiempo pasado historico"),
    Entrada("ia", "Predicciones IA", "Modelos que aprenden del mercado y por qué deciden", "/ia", "pagina",
            "inteligencia artificial prediccion"),
    Entrada("como-funciona", "Cómo funciona", "Las estructuras de datos de la plataforma, en vivo", "/como-funciona",
            "pagina", "estructuras datos"),
    Entrada("seguridad", "Seguridad", "Dispositivos, actividad y contraseña", "/seguridad", "pagina", "cuenta"),
    # ---------- acciones ----------
    Entrada("comprar", "Comprar bitcoin", "Crear una orden de compra con USDT de práctica", "/ordenes", "accion",
            "btc invertir"),
    Entrada("vender", "Vender bitcoin", "Crear una orden de venta", "/ordenes", "accion", "btc"),
    Entrada("deshacer", "Deshacer la última orden", "Ctrl + Z en Órdenes: saca la última de la pila", "/ordenes",
            "accion", "ctrl z pila"),
    Entrada("encender-bot", "Encender el bot", "Que el bot decida y opere por ti", "/bot", "accion", "iniciar"),
    Entrada("dos-pasos", "Verificación en dos pasos", "Activar Google Authenticator", "/seguridad", "accion",
            "2fa totp autenticador"),
    Entrada("contrasena", "Cambiar la contraseña", "Desde el centro de seguridad", "/seguridad", "accion", "clave"),
    Entrada("sesiones", "Cerrar sesiones abiertas", "Ver y cerrar tus dispositivos", "/seguridad", "accion",
            "dispositivos"),
    # ---------- indicadores ----------
    Entrada("rsi", "RSI", "Índice de fuerza relativa: sobrecompra sobre 70, sobreventa bajo 30", "/mercado",
            "indicador", "fuerza relativa oscilador"),
    Entrada("macd", "MACD", "Diferencia entre dos medias exponenciales y su señal", "/mercado", "indicador",
            "oscilador"),
    Entrada("sma", "SMA", "Media móvil simple", "/mercado", "indicador", "media movil promedio"),
    Entrada("ema", "EMA", "Media móvil exponencial", "/mercado", "indicador", "media movil exponencial"),
    Entrada("bollinger", "Bandas de Bollinger", "Media ± 2 desviaciones: qué tan lejos se fue el precio", "/mercado",
            "indicador", "volatilidad"),
    # ---------- conceptos ----------
    Entrada("comision", "Comisión", "Cada compra y venta paga 0,1 %", "/como-funciona", "concepto", "fee"),
    Entrada("stop-loss", "Stop-loss", "Vende todo si el precio cae cierto porcentaje", "/bot", "concepto",
            "perdida limite"),
    Entrada("take-profit", "Take-profit", "Vende todo al subir cierto porcentaje", "/bot", "concepto", "ganancia"),
    Entrada("cola", "Cola (FIFO)", "Las órdenes pendientes se ejecutan en orden de llegada", "/como-funciona#cola",
            "concepto", "fifo estructura"),
    Entrada("pila", "Pila (LIFO)", "El historial y el deshacer: lo último queda arriba", "/como-funciona#pila",
            "concepto", "lifo estructura"),
    Entrada("monticulo", "Montículo", "Cola de prioridad: arma la liga de inversores", "/como-funciona#monticulo",
            "concepto", "heap prioridad estructura"),
    Entrada("avl", "Árbol AVL", "Árbol de búsqueda balanceado: indexa las velas por fecha", "/como-funciona#avl",
            "concepto", "arbol balanceado rotacion estructura"),
    Entrada("tabla-hash", "Tabla hash", "Encuentra la simulación de cada usuario en O(1)",
            "/como-funciona#tabla-hash", "concepto", "hash mapa estructura"),
    Entrada("cola-circular", "Cola circular", "Guarda los últimos precios con memoria fija",
            "/como-funciona#cola-circular", "concepto", "anillo buffer estructura"),
    Entrada("trie", "Trie", "Árbol de prefijos: esta misma búsqueda", "/como-funciona#trie", "concepto",
            "prefijo autocompletar estructura"),
    Entrada("rentabilidad", "Rentabilidad", "Cuánto ganaste o perdiste frente a tu saldo inicial", "/cartera",
            "concepto", "ganancia retorno"),
    Entrada("costo-promedio", "Costo promedio", "Lo que pagaste en promedio por tu BTC, con comisiones", "/cartera",
            "concepto", "precio compra"),
)
