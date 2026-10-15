# API HTTP

Servidor en Python con **FastAPI** sobre **uvicorn** (antes era Java con `com.sun.net.httpserver`; el contrato no cambió). Todas las respuestas con cuerpo son `application/json; charset=utf-8`, también los errores.

## Arrancar el servidor (Python)

Requisito: Python 3.13. Desde la raíz del repo:

```bash
py -3.13 -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -e ".[dev]"
```

```bash
python -m bitcoinai
```

- **Activar el entorno:** el segundo comando es para Windows; en Linux o macOS es `source .venv/bin/activate`.
- **Dónde queda:** en `http://localhost:8080`, o en el puerto de la variable `PORT`. Ctrl+C lo apaga.
- **Documentación interactiva:** FastAPI la publica en **`/docs`** (por ejemplo `http://localhost:8080/docs`). Ahí se ven todos los endpoints con sus parámetros y se pueden probar desde el navegador. El esquema OpenAPI está en `/openapi.json`.
- **Números:** pueden venir como `100` o `100.0` según el valor; en JSON son el mismo número.
- **Ejemplos de esta página:** salieron de la versión Java. La versión Python devuelve las mismas claves en el mismo orden, y los valores calculados coinciden porque se portaron los mismos algoritmos y pruebas.

## Convenciones

- **Errores:** siempre con la forma `{"error": "mensaje"}`.

| Código | Cuándo |
| --- | --- |
| 400 | Parámetro inválido; el mensaje dice cuál y por qué |
| 404 | La ruta no existe |
| 405 | La ruta existe pero no con ese método; incluye el encabezado `Allow` |
| 401, 409, 429 | Cuentas y sesión: ver [Cuentas y seguridad](#cuentas-y-seguridad) |
| 502 | La fuente de mercado (Binance) falló: `{"error":"Fuente de mercado no disponible"}` |
| 500 | Error inesperado: `{"error":"Error interno del servidor"}`, sin detalles ni trazas |

- **CORS:** todas las respuestas llevan `Access-Control-Allow-Origin` con el valor de `ORIGEN_PERMITIDO`. Las peticiones `OPTIONS` (preflight) reciben `204` sin cuerpo. Con un origen concreto (no `*`) también llevan `Access-Control-Allow-Credentials: true`, para que el navegador envíe la cookie de sesión.
- **Encabezados de seguridad:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (salvo en `/docs`), `Referrer-Policy: no-referrer` y, con `COOKIE_SEGURA=true`, `Strict-Transport-Security`.
- **Barra final:** se ignora; `/health/` es lo mismo que `/health`.
- **Registro:** cada petición deja una línea en la consola del servidor, por ejemplo `GET /api/velas 200 35 ms`.
- **Caché:** el precio y las velas se guardan en memoria `TTL_CACHE_SEGUNDOS` segundos, así que dos peticiones iguales seguidas solo consultan Binance una vez.

## Endpoints

### `GET /health`

Indica que el servicio está vivo. Responde siempre rápido y nunca consulta Binance (Railway lo usa como healthcheck).

```json
{"estado":"ok"}
```

### `GET /api/precio`

Último precio negociado del símbolo configurado.

```json
{"simbolo":"BTCUSDT","precio":83097.08,"momento":1791417600000}
```

`momento` es la hora del servidor al responder, en milisegundos desde 1970 (UTC).

### `GET /api/precio/recientes`

Los últimos precios que pasaron por el servidor, del más viejo al más nuevo. No consulta Binance: los guarda una **cola circular** de 120 casillas que alimentan `GET /api/precio` y el tiempo real (cada 5 s). Al llenarse, cada precio nuevo pisa al más viejo, así que son más o menos los últimos 10 minutos. Si llegan dos con menos de 2 s entre sí, se guarda solo el primero.

```json
{"simbolo":"BTCUSDT","capacidad":120,"cantidad":2,
 "precios":[{"momento":1791417600000,"precio":83097.08},{"momento":1791417605000,"precio":83101.5}]}
```

Está vacía hasta que alguien pide el precio o se conecta a `/api/stream`.

### `GET /api/velas`

Velas del símbolo configurado, de la más antigua a la más reciente.

| Parámetro | Valores | Por defecto |
| --- | --- | --- |
| `intervalo` | `1m`, `5m`, `15m`, `1h`, `4h`, `1d` | `1d` |
| `cantidad` | entero entre 1 y 1000 | `200` |

Ejemplo: `GET /api/velas?intervalo=1d&cantidad=2`

```json
{
  "simbolo": "BTCUSDT",
  "intervalo": "1d",
  "cantidad": 2,
  "velas": [
    {"tiempoApertura":1791244800000,"apertura":85766.87,"maximo":86698.99,"minimo":85136.11,
     "cierre":85549.93,"volumen":12614.48,"tiempoCierre":1791331199999},
    {"tiempoApertura":1791331200000,"apertura":85549.94,"maximo":85598.22,"minimo":82787.25,
     "cierre":83321.81,"volumen":20838.08,"tiempoCierre":1791417599999}
  ]
}
```

- Los tiempos están en milisegundos desde 1970 (UTC). El volumen está en BTC.
- La última vela puede estar todavía abierta (la del periodo en curso).
- `cantidad` en la respuesta es el número de velas devueltas: puede ser menor que lo pedido si no hay tanto historial.

Errores de ejemplo:

```json
{"error":"Parámetro 'intervalo' inválido: '2h'. Valores permitidos: 1m, 5m, 15m, 1h, 4h, 1d"}
{"error":"Parámetro 'cantidad' inválido: '5000'. Debe ser un número entero entre 1 y 1000"}
```

### `GET /api/indicadores`

Calcula un indicador técnico sobre los cierres de las velas y devuelve sus series junto con las velas usadas.

| Parámetro | Valores | Por defecto |
| --- | --- | --- |
| `indicador` | `sma`, `ema`, `rsi`, `macd`, `bollinger`, `volatilidad` | obligatorio |
| `intervalo` | `1m`, `5m`, `15m`, `1h`, `4h`, `1d` | `1d` |
| `cantidad` | entero entre 1 y 1000 (velas usadas) | `200` |
| `periodo` | entero entre 2 y 1000 (sma, ema, rsi, bollinger, volatilidad) | sma/ema/bollinger/volatilidad `20`, rsi `14` |
| `rapido`, `lento`, `senal` | enteros entre 2 y 1000, con `lento` > `rapido` (solo macd) | `12`, `26`, `9` |
| `desviaciones` | número mayor que 0 y hasta 10 (solo bollinger) | `2` |

Los parámetros que no corresponden al indicador se ignoran. En `parametros` la respuesta muestra los valores que se usaron de verdad.

**Series que devuelve cada indicador:**

| Indicador | Series | Qué es |
| --- | --- | --- |
| `sma` | `valor` | Media móvil simple de los últimos `periodo` cierres |
| `ema` | `valor` | Media móvil exponencial, α = 2/(periodo+1), inicializada con la SMA |
| `rsi` | `valor` | Índice de Fuerza Relativa (0 a 100) con suavizado de Wilder; una serie plana da 50 |
| `macd` | `macd`, `senal`, `histograma` | EMA rápida − EMA lenta, su EMA de señal, y la diferencia entre ambas |
| `bollinger` | `media`, `superior`, `inferior` | SMA ± `desviaciones`·σ (desviación poblacional) |
| `volatilidad` | `valor` | Desviación estándar muestral de los retornos logarítmicos, por vela (no anualizada) |

- **Calentamiento:** las primeras velas no generan punto mientras no hay datos suficientes, así que las series tienen menos puntos que velas. Por ejemplo, el RSI 14 de 200 velas da 186 puntos.
- **Alineación:** cada punto lleva el `tiempo` de apertura de su vela, para alinearlo con `velas` en un gráfico.
- **Periodo grande:** si el periodo es mayor que las velas disponibles, la serie viene vacía (no es un error).
- **`maximaCaida`:** la mayor caída porcentual del cierre desde un pico en esas velas (`caidaMaxima` es una fracción: 0,25 = −25 %), con el pico y el valle.

Ejemplo real (recortado): `GET /api/indicadores?indicador=rsi&periodo=14&intervalo=1d&cantidad=200` devolvió 200 velas y 186 puntos de RSI.

```json
{
  "simbolo": "BTCUSDT",
  "intervalo": "1d",
  "indicador": "rsi",
  "parametros": {"periodo": 14},
  "series": {
    "valor": [
      {"tiempo": 1775433600000, "valor": 41.73851100906724},
      {"tiempo": 1775520000000, "valor": 53.98575506084686},
      "...",
      {"tiempo": 1791417600000, "valor": 52.64482306926816}
    ]
  },
  "maximaCaida": {"caidaMaxima": 0.2868913747427779, "tiempoPico": 1778371200000, "valorPico": 82210.07,
                  "tiempoValle": 1782777600000, "valorValle": 58624.71},
  "cantidad": 200,
  "velas": [
    {"tiempoApertura": 1774224000000, "apertura": 67859, "maximo": 71817.09, "minimo": 67445.18,
     "cierre": 70906.45, "volumen": 28335.09119, "tiempoCierre": 1774310399999},
    "..."
  ]
}
```

Errores de ejemplo (400; se valida todo antes de consultar Binance):

```json
{"error":"Falta el parámetro 'indicador'. Valores permitidos: sma, ema, rsi, macd, bollinger, volatilidad"}
{"error":"Parámetro 'periodo' inválido: '1'. Debe ser un número entero entre 2 y 1000"}
{"error":"Parámetro 'lento' (12) debe ser mayor que 'rapido' (26)"}
```

### `GET /api/si-hubiera`

**¿Y si hubiera invertido?** Calcula cuánto valdría hoy una compra hecha al abrir un día del pasado. Es un cálculo hipotético con datos reales, no una predicción.

| Parámetro | Valores | Ejemplo |
| --- | --- | --- |
| `fecha` | `AAAA-MM-DD`, en UTC y no en el futuro | `2024-01-15` |
| `monto` | USDT, mayor que 0 y hasta 1 000 000 | `1000` |

**Cómo funciona:**
- Las últimas 1000 velas diarias se indexan en un **árbol AVL** por su hora de apertura.
- `techo(fecha)` encuentra la primera vela desde esa fecha en O(log n).
- `rango(fecha, hoy)` recorre solo las velas posteriores para hallar el mejor (máximo) y el peor (mínimo) momento.
- La compra descuenta la comisión de 0,1 %.

```json
{"fecha":"2024-01-15","monto":1000,"vela":{"tiempoApertura":1705276800000,"apertura":42499.99,…},
 "btc":0.0235059,"precioActual":82937.59,"valorHoy":1949.52,"ganancia":949.52,"rentabilidad":0.9495,
 "mejor":{"tiempo":1734307200000,"precio":108353.0},"peor":{"tiempo":1705795200000,"precio":38555.0},
 "velasRecorridas":636,"alturaArbol":11,"velasIndexadas":1000}
```

Si la fecha es anterior a los datos, responde `400` con el día desde el que hay datos: `"Esa fecha es anterior a los datos disponibles. Hay datos desde el 2024-01-17."`.

### `GET /api/buscar`

La búsqueda de **Ctrl + K**: páginas, acciones, indicadores y conceptos de la plataforma. Es pública, porque el catálogo no tiene nada privado.

| Parámetro | Valores | Ejemplo |
| --- | --- | --- |
| `q` | Texto de hasta 60 caracteres | `órde` |
| `limite` | Entero entre 1 y 20 (por defecto 8) | `5` |

**Cómo funciona:**
- Cada palabra del catálogo, en minúsculas y sin tildes, está en un **trie**. Por eso no importa cómo se escriba: "ÓRDE" encuentra "Órdenes".
- Cada palabra de `q` se toma como prefijo, y una entrada aparece solo si coincide con todas.
- Una **tabla hash** junta los resultados sin repetirlos.
- Primero salen las entradas que coinciden en el título.

```json
{"consulta":"órde","resultados":[{"id":"ordenes","titulo":"Órdenes","descripcion":"Comprar, vender y la cola de pendientes","ruta":"/ordenes","tipo":"pagina"}],
 "palabrasIndexadas":222,"nodosTrie":886}
```

`tipo` es `pagina`, `accion`, `indicador` o `concepto`. `nodosTrie` es menor que la suma de las letras de todas las palabras, porque las que empiezan igual comparten nodos.

## Estrategias, señales y backtest

> **Aviso:** Resultado de pruebas con datos históricos; no es asesoría financiera ni garantiza ganancias. Ese texto viaja en el campo `aviso` de cada pronóstico y de cada backtest.

### Estrategias disponibles

| `estrategia` | Compra cuando… | Vende cuando… | Parámetros (por defecto) |
| --- | --- | --- | --- |
| `cruce` | la SMA corta cruza hacia arriba la larga | la cruza hacia abajo | `corta` (20), `larga` (50) |
| `rsi` | el RSI estuvo bajo `sobreventa` y vuelve a subir por encima | estuvo sobre `sobrecompra` y vuelve a bajar | `periodo` (14), `sobreventa` (30), `sobrecompra` (70) |
| `macd` | el MACD cruza hacia arriba su señal | la cruza hacia abajo | `rapido` (12), `lento` (26), `senal` (9) |
| `combinada` | votación ponderada de las tres anteriores | ídem | `pesoCruce`, `pesoRsi`, `pesoMacd` (1 cada uno, entre 0 y 10), más los parámetros de las tres |

**Cuándo dan señal:**
- Cada estrategia da COMPRAR o VENDER solo en la vela del cruce. El resto del tiempo dice MANTENER con confianza 0,25.
- La confianza de una señal va de 0,6 a 1 y crece con lo marcado del cruce.
- Con menos velas de las necesarias, la estrategia dice MANTENER con confianza 0.

**Cómo vota la combinada:**
- El puntaje de cada señal es la suma de peso × confianza de las estrategias que la votaron, dividida entre la suma de los pesos.
- Gana la señal con más puntaje, y ese puntaje es su confianza.
- Si MANTENER empata con otra señal, gana MANTENER.
- Si COMPRAR y VENDER empatan, las estrategias se contradicen y la combinada dice MANTENER.

**Velas en curso:** `/api/senal` y `/api/backtest` descartan la vela que todavía no cerró, porque su valor aún cambia y una señal sobre ella podría desaparecer.

### `GET /api/senal`

Decisión y pronóstico más recientes.

| Parámetro | Valores | Por defecto |
| --- | --- | --- |
| `estrategia` | `cruce`, `rsi`, `macd`, `combinada` | `combinada` |
| `intervalo` | `1m`, `5m`, `15m`, `1h`, `4h`, `1d` | `1d` |
| `cantidad` | velas a pedir, entre 1 y 1000 | `200` |
| parámetros de la estrategia | ver la tabla de estrategias | |

**El pronóstico:**
- `direccion` sale de la señal: COMPRAR → `SUBE`, VENDER → `BAJA`, MANTENER → `LATERAL`.
- `justificacion` tiene las frases de las estrategias que votaron lo mismo que la decisión final.
- `indicadores` tiene el último valor de cada indicador usado.

Ejemplo real: `GET /api/senal?estrategia=combinada&intervalo=1d`

```json
{
  "simbolo": "BTCUSDT", "intervalo": "1d", "estrategia": "combinada",
  "parametros": {"pesos": {"cruce": 1, "rsi": 1, "macd": 1}, "estrategias": {"...": "..."}},
  "velasAnalizadas": 199,
  "decision": {"tiempo": 1791331200000, "senal": "MANTENER", "precio": 83321.81, "confianza": 0.25,
               "motivo": "Votación ponderada: COMPRAR 0.00, VENDER 0.00, MANTENER 0.25; gana MANTENER."},
  "pronostico": {
    "direccion": "LATERAL",
    "confianza": 0.25,
    "justificacion": [
      "cruce: Sin cruce nuevo: la SMA 20 (84203.04) sigue por encima de la SMA 50 (80296.84).",
      "rsi: El RSI (52.94) está en zona neutral, sin señal de giro.",
      "macd: Sin cruce nuevo: el MACD sigue por debajo de su señal (MACD 1687.76, señal 1966.68)."
    ],
    "indicadores": {"smaCorta": 84203.04, "smaLarga": 80296.84, "rsi": 52.94,
                    "macd": 1687.76, "senalMacd": 1966.68, "histogramaMacd": -278.92},
    "aviso": "Resultado de pruebas con datos históricos; no es asesoría financiera ni garantiza ganancias"
  }
}
```

### `GET /api/backtest`

Simula la estrategia sobre velas históricas y la valida con una división entrenamiento/prueba.

| Parámetro | Valores | Por defecto |
| --- | --- | --- |
| `estrategia` | `cruce`, `rsi`, `macd`, `combinada` | `combinada` |
| `capital` | USDT iniciales, entre 1 y 1 000 000 000 | `1000` |
| `comision` | por operación, entre 0 y 0.05 | `0.001` (0,1 %) |
| `entrenamiento` | fracción para entrenar, entre 0.5 y 0.9 | `0.7` |
| `intervalo` | `1m`, `5m`, `15m`, `1h`, `4h`, `1d` | `1d` |
| `cantidad` | velas, entre 1 y 1000 | `1000` |
| parámetros de la estrategia | ver la tabla de estrategias | |

**Reglas de la simulación:**
- **Sin mirar el futuro:** en cada vela la estrategia solo recibe las velas hasta esa.
- **Ejecución honesta:** decide con el cierre de una vela y la orden se ejecuta en la apertura de la siguiente.
- **Solo posiciones largas:** COMPRAR sin posición invierte todo el efectivo; VENDER con posición vende todo; las demás señales se ignoran.
- **Comisión:** se cobra en cada compra y en cada venta, sobre el monto operado.
- **Cierre final:** una posición abierta al final se cierra al último cierre.

**Respuesta:** `{simbolo, intervalo, estrategia, parametros, resultado, validacion, aviso}`.

- **`resultado`:** backtest con los parámetros pedidos sobre todas las velas.

  | Campo | Qué es |
  | --- | --- |
  | `capitalFinal` | USDT al terminar, con la posición cerrada |
  | `rentabilidadTotal` | rentabilidad de la estrategia |
  | `rentabilidadComprarYMantener` | comprar en la primera apertura y vender en el último cierre, con comisiones; es la referencia a superar |
  | `numeroOperaciones` | operaciones cerradas |
  | `tasaGanadoras` | fracción de operaciones con ganancia |
  | `caidaMaxima` | mayor caída de la curva de capital desde un pico |
  | `factorBeneficio` | ganancias / pérdidas; `null` si no hubo pérdidas |
  | `comisionesPagadas` | total de comisiones en USDT |
  | `operaciones` | cada compra-venta |
  | `decisionesRecientes` | últimas 20 decisiones de comprar o vender, de la más nueva a la más vieja; salen de una Pila |
  | `curvaCapital` | valor de la cartera al cierre de cada vela |

  Las rentabilidades, la tasa y la caída son fracciones: 0,35 = 35 %.
- **`validacion`:**
  - Divide las velas en entrenamiento (70 %) y prueba (30 %).
  - Prueba varias combinaciones de parámetros **solo con las velas de entrenamiento** y elige la de mayor rentabilidad (`parametrosElegidos`, `candidatos`).
  - Informa cómo rinde esa elección en el 30 % final, que nunca participó en la elección (`prueba`).
  - En la prueba, las velas de entrenamiento solo sirven para calentar los indicadores.
  - La validación busca sus propios parámetros, así que ignora los que vengan en la URL.

  | Estrategia | Combinaciones probadas |
  | --- | --- |
  | cruce | 9: corta {5, 10, 20} × larga {30, 50, 100} |
  | rsi | 9: periodo {7, 14, 21} × niveles {30/70, 25/75, 20/80} |
  | macd | 3: 12/26/9, 8/17/9, 5/35/5 |
  | combinada | 4: pesos 1/1/1, 2/1/1, 1/2/1, 1/1/2 |

**Cómo leer el resultado:** si la estrategia rinde mucho mejor en entrenamiento que en prueba, sus parámetros se ajustaron al pasado (sobreajuste).

Resultados reales con 999 velas diarias de BTCUSDT, capital 1000 y comisión 0,1 %, medidos el 2026-10-07:

| Estrategia | Rentabilidad | Comprar y mantener | Operaciones | Ganadoras | Caída máx. | Validación: entrenamiento → prueba (comprar y mantener en prueba: −10,1 %) |
| --- | --- | --- | --- | --- | --- | --- |
| cruce | +35,0 % | +94,4 % | 11 | 55 % | 31,3 % | +44,1 % → +5,3 % |
| rsi | +36,3 % | +94,4 % | 4 | 100 % | 28,7 % | +120,9 % → **−12,2 %** (sobreajuste) |
| macd | +36,9 % | +94,4 % | 39 | 36 % | 34,6 % | +32,6 % → +10,8 % |
| combinada | +72,5 % | +94,4 % | 40 | 48 % | 23,1 % | +63,7 % → +13,0 % |

En todo el periodo, ninguna estrategia superó a comprar y mantener.

## Inteligencia artificial: `GET /api/ia/predicciones`

Tres modelos hechos a mano y un comité dicen si la próxima vela cerrará más arriba. Es pública. Ver [docs/IA.md](IA.md).

| Parámetro | Valores | Por defecto |
| --- | --- | --- |
| `intervalo` | `15m`, `1h`, `4h`, `1d` | `1h` |

- **Datos:** se toman las últimas 1000 velas cerradas. Los modelos se entrenan con el 80 % más viejo y se miden con el 20 % más reciente, que no vieron. El modelo que predice es el mismo que se midió.
- **Caché:** la primera petición de cada intervalo entrena, y tarda unos segundos. Las siguientes, durante 10 minutos, salen de la caché (`entrenadoEn` no cambia).
- **Métricas:**
  - `exactitud`: aciertos ÷ predicciones.
  - `base`: lo que acertaría decir siempre lo que más pasó en esas mismas velas.
  - `ventaja`: `exactitud − base`. Si es negativa, al modelo le fue peor que no hacer nada.
  - `precisionSube`: de las veces que dijo "sube", qué fracción subió. Es `null` si nunca lo dijo.
- **`explicacion.factores`:** su significado depende del modelo:
  - Regresión logística: el aporte de cada característica (positivo empuja a subir).
  - Árbol: cuánto bajó el Gini gracias a cada característica (suman 1).
  - k vecinos: cuántas desviaciones se aleja la vela de ahora del promedio.
  - Comité: cuánto empuja cada miembro.
- **`arbol`:** el árbol entrenado, con `enCamino` en las ramas por las que pasó la vela de ahora.
- **`prueba`:** lo que dijo el comité en cada vela de prueba y si subió.

```json
{"simbolo":"BTCUSDT","intervalo":"1h","tiempoVela":1791820800000,"entrenadoEn":1791824400000,
 "muestrasEntrenamiento":759,"muestrasPrueba":190,
 "comite":{"nombre":"Comité","probabilidad":0.53,"direccion":"SUBE","confianza":0.06,"peso":null,
   "explicacion":{"resumen":"2 de 3 modelos creen que sube; el que más pesa es k vecinos.","factores":[…],"pasos":[…]},
   "metricas":{"muestras":190,"exactitud":0.53,"base":0.51,"ventaja":0.02,"precisionSube":0.54,"vecesDijoSube":120}},
 "modelos":[{"nombre":"Regresión logística",…,"peso":0.31},{"nombre":"Árbol de decisión",…},{"nombre":"k vecinos",…}],
 "caracteristicas":[{"nombre":"Rendimiento de la última vela","valor":-0.0012},…],
 "arbol":{"hoja":false,"caracteristica":"RSI 14","umbral":31.9,"muestras":759,"probabilidad":0.51,"enCamino":true,"si":{…},"no":{…}},
 "prueba":[{"tiempo":1791140400000,"probabilidad":0.55,"subio":true},…],
 "aviso":"Predicción hecha con datos reales del pasado. … No es asesoría financiera."}
```

Responde `400` si el intervalo no está permitido, `502` si Binance no responde y `503` si no hay velas suficientes (hacen falta al menos 200 muestras).

## Simulación de operaciones (paper trading)

> **Todo es simulado:** no hay dinero real, ni conexión a una cuenta de exchange, ni claves de API. El único dato externo es el precio público de Binance, que se usa para ejecutar las órdenes simuladas.

> **Cada usuario tiene su propia simulación** (cartera, órdenes, historial y bot). Todos los endpoints de esta sección **exigen sesión**: sin la cookie responden `401` `{"error":"Tu sesión terminó; vuelve a iniciar sesión"}`, y la sesión se revisa antes que el cuerpo. Un usuario nunca ve ni toca las órdenes de otro: para él, la orden #1 de otra persona no existe (`404`).

**Cómo funciona:**
- **Cartera:** cada cuenta empieza con 10 000 USDT y 0 BTC. Cada compra y cada venta paga una comisión de 0,1 %.
- **Cola de pendientes:** cada orden nueva espera en una **Cola** y se ejecuta en orden de llegada (FIFO), al precio actual.
- **Registro:** las órdenes terminadas (ejecutadas, canceladas o rechazadas) quedan en una **Lista**.
- **Historial:** cada evento se apila en una **Pila**, con el más reciente arriba.
- **Quién ejecuta:** con el bot detenido, las órdenes se ejecutan con `POST /api/ordenes/procesar`. Con el bot en marcha, al final de cada ciclo procesa la cola entera, incluidas las órdenes manuales.
- **Bot:** cada usuario enciende el suyo. Como cada bot consulta el mercado periódicamente, hay como máximo `MAX_BOTS` encendidos a la vez entre todos (por defecto 20); si se llega al límite, `POST /api/bot/iniciar` responde `409`.
- **Persistencia:** la simulación de cada usuario se guarda en la base de datos después de cada cambio y se recupera al reiniciar (ver [Persistencia](#persistencia)).

**Estados de una orden:**

| Estado | Significado |
| --- | --- |
| `PENDIENTE` | En la cola |
| `PROCESANDO` | Fuera de la cola, consultando el precio; ya no se puede cancelar |
| `EJECUTADA` | La cartera ya cambió |
| `CANCELADA` | Cancelada o deshecha antes de ejecutarse |
| `RECHAZADA` | Saldo o BTC insuficiente; el motivo va en `detalle` |

**Campos de una orden:** `id`, `tipo`, `monto`, `todo`, `estado`, `creadaEn`, `ejecutadaEn`, `precioEjecucion`, `cantidadBtc`, `comision`, `motivo` (`manual`, `señal del bot: …`, `stop-loss: …`) y `detalle`.

**Errores de esta sección:**

| Código | Cuándo |
| --- | --- |
| 400 | Datos inválidos; el mensaje dice cuál |
| 404 | La orden no existe |
| 401 | No hay sesión |
| 409 | El estado no lo permite: cancelar algo ya ejecutado, procesar con la cola vacía, iniciar el bot dos veces, o ya hay `MAX_BOTS` bots en marcha |
| 502 | No se pudo obtener el precio; la orden vuelve al frente de la cola, pendiente |

### Órdenes

| Método y ruta | Qué hace | Respuesta |
| --- | --- | --- |
| `POST /api/ordenes` | Crea una orden pendiente (cuerpo abajo) | 201 con la orden |
| `GET /api/ordenes?estado=PENDIENTE` | Lista órdenes: pendientes en orden de cola, la que se procesa y luego el registro. `estado` es opcional | `{"cantidad":n,"ordenes":[…]}` |
| `GET /api/ordenes/{id}` | Una orden | la orden |
| `DELETE /api/ordenes/{id}` | Cancela una orden pendiente (reconstruye la cola sin ella, O(n)) | la orden cancelada |
| `POST /api/ordenes/procesar` | Ejecuta la orden del frente de la cola | la orden ejecutada o rechazada |
| `POST /api/ordenes/deshacer` | Deshace la última orden creada si sigue pendiente; repetirlo deshace la anterior | la orden deshecha |

Cuerpo de `POST /api/ordenes`:

```json
{"tipo": "COMPRA", "monto": 500}
{"tipo": "VENTA",  "monto": 200}
{"tipo": "VENTA",  "todo": true, "motivo": "tomo ganancias"}
```

- `tipo` es obligatorio: `COMPRA` o `VENTA`.
- `monto` es obligatorio salvo con `todo`. Son USDT, mayor que 0. En la compra son los USDT a gastar, comisión incluida. En la venta es el valor del BTC a vender.
- `todo` (opcional, solo en VENTA, sin `monto`) vende todo el BTC que haya al ejecutarse.
- `motivo` es opcional (por defecto `manual`).

Ejemplo real de una compra ya ejecutada:

```json
{"id": 1, "tipo": "COMPRA", "monto": 500, "todo": false, "estado": "EJECUTADA",
 "creadaEn": 1791433083000, "ejecutadaEn": 1791433083120, "precioEjecucion": 82937.59,
 "cantidadBtc": 0.00602260084962681, "comision": 0.5, "motivo": "manual",
 "detalle": "Compró 0.00602260 BTC a 82937.59 por 500.00 USDT (comisión 0.50 USDT)."}
```

### Cartera e historial

`GET /api/cartera` valora la cartera al precio actual. Ejemplo real, después de la compra anterior:

```json
{"precioActual": 82937.59, "saldoUsdt": 9500, "btc": 0.00602260084962681,
 "costoPromedio": 83020.61, "valorBtc": 499.5, "valorTotal": 9999.5,
 "gananciaNoRealizada": -0.5, "gananciaRealizada": 0, "gananciaTotal": -0.5,
 "rentabilidad": -0.00005, "comisionesPagadas": 0.5, "saldoInicial": 10000}
```

- **`costoPromedio`:** incluye las comisiones de compra. Una venta parcial no lo cambia.
- **`gananciaRealizada`:** la de las ventas ya hechas.
- **`gananciaTotal`:** `valorTotal − saldoInicial`.

`GET /api/historial?limite=50` (entre 1 y 500) devuelve `{"eventos":[…]}` del más reciente al más viejo. Cada evento es `{momento, tipo, idOrden, descripcion}`.

Tipos de evento:

| Grupo | Tipos |
| --- | --- |
| Órdenes | `ORDEN_CREADA`, `ORDEN_EJECUTADA`, `ORDEN_CANCELADA`, `ORDEN_DESHECHA`, `ORDEN_RECHAZADA` |
| Bot | `DECISION_BOT`, `STOP_LOSS`, `TAKE_PROFIT`, `BOT_INICIADO`, `BOT_DETENIDO`, `ERROR_BOT` |

### Liga de inversores: `GET /api/liga`

Los 10 usuarios con mejor rentabilidad y tu puesto. Exige sesión.

- **Quién entra:** quien ya ejecutó al menos una orden. Cada cartera se valora al precio actual.
- **Privacidad:** nadie aparece con su nombre. Cada usuario tiene un **alias** fijo, por ejemplo `Halcón Dorado 07`, y `esTuyo` marca el tuyo.
- **Cómo se calcula:** un **montículo** de tamaño 10 guarda los 10 mejores vistos hasta el momento, y su tope es el peor de ellos. Cada usuario nuevo entra solo si supera ese tope. Cuesta O(n log 10), sin ordenar a todos.
- **Empates:** gana quien se registró antes.

```json
{"precio": 120.0, "participantes": 2,
 "mejores": [{"posicion": 1, "alias": "Halcón Dorado 07", "rentabilidad": 0.0994, "valorTotal": 10994.0, "esTuyo": true},
             {"posicion": 2, "alias": "Lince Jade 41", "rentabilidad": 0.0198, "valorTotal": 10198.0, "esTuyo": false}],
 "tu": {"posicion": 1, "alias": "Halcón Dorado 07", "rentabilidad": 0.0994, "valorTotal": 10994.0, "esTuyo": true}}
```

`tu` es `null` si todavía no has ejecutado ninguna orden.

### Alertas de precio

Exigen sesión. Cada usuario puede tener hasta 20 alertas activas.

| Método y ruta | Qué hace | Respuesta |
| --- | --- | --- |
| `POST /api/alertas` | `{"tipo":"SUBE_A","precio":90000}` o `{"tipo":"BAJA_A","precio":75000}` | 201 con la alerta |
| `GET /api/alertas` | Las 50 más nuevas del usuario | `{"activas":n,"alertas":[…]}` |
| `DELETE /api/alertas/{id}` | Cancela una alerta activa propia | 204 (404 si no existe, no es tuya o ya no está activa) |

- **Validación:** `SUBE_A` debe estar por encima del precio actual y `BAJA_A` por debajo. Una alerta que ya se cumple no sirve (responde `400`).
- **Campos:** `id`, `tipo`, `precio`, `estado` (`ACTIVA`, `DISPARADA` o `CANCELADA`), `creadaEn`, `disparadaEn` y `precioDisparo`.

**Cómo se disparan:**
- Las activas de todos los usuarios están en **dos montículos**. Las `SUBE_A` van en uno de mínimos, porque la más baja es la primera que se cumple al subir. Las `BAJA_A` van en uno de máximos.
- Un vigilante revisa el precio cada 10 s, y solo si hay alertas activas. Saca de los topes las que se cumplen, en O(k log n).
- Cancelar es perezoso: la alerta se marca en una tabla hash y se descarta cuando llega al tope.
- Al cumplirse, su dueño recibe `event: alerta` por `/api/stream` con la alerta ya disparada.

### Bot simulado

| Método y ruta | Qué hace |
| --- | --- |
| `POST /api/bot/iniciar` | Lo pone en marcha; el primer ciclo es inmediato. Cuerpo opcional (abajo). 409 si ya estaba en marcha |
| `POST /api/bot/detener` | Lo detiene (si ya estaba detenido, no hace nada) |
| `GET /api/bot/estado` | `{activo, estrategia, configuracion, ciclos, ultimoCiclo, ultimaDecision, ultimoError, encendidoDesde, enCiclo}`. `encendidoDesde` es cuándo se encendió (ms, `null` si está detenido) y `enCiclo` es `true` mientras revisa el mercado |

Cuerpo de `iniciar`; todos los campos son opcionales:

```json
{"segundosEntreCiclos": 60, "intervalo": "1h", "cantidadVelas": 200,
 "riesgo": 0.2, "stopLoss": 0.05, "takeProfit": 0.10}
```

| Campo | Qué es | Rango |
| --- | --- | --- |
| `segundosEntreCiclos` | Cada cuánto decide | entero entre 1 y 86 400 |
| `intervalo` | Intervalo de las velas que analiza | `1m`, `5m`, `15m`, `1h`, `4h`, `1d` |
| `cantidadVelas` | Cuántas velas analiza | entre 2 y 1000 |
| `riesgo` | Fracción del saldo por compra | mayor que 0 y hasta 1 |
| `stopLoss` | Caída desde el costo promedio que dispara la venta | entre 0 y 1, sin incluirlos |
| `takeProfit` | Subida desde el costo promedio que dispara la venta | mayor que 0 y hasta 10 |

En cada ciclo el bot:
1. Pide las velas cerradas más recientes y el precio actual.
2. Consulta la estrategia combinada y anota su decisión con el motivo (`DECISION_BOT`).
3. **Stop-loss y take-profit**, que tienen prioridad: con posición abierta, si el precio cayó `stopLoss` o más desde el costo promedio, o subió `takeProfit` o más, vende todo el BTC.
4. Si no se activó ninguno: con COMPRAR y sin posición, compra por `riesgo` × saldo; con VENDER y con posición, vende todo.
5. Procesa la cola de pendientes.

Si un ciclo falla (por ejemplo, Binance no responde), queda en `ultimoError` y en el historial, y el bot sigue con el siguiente.

### Probar con curl

En PowerShell 5.1, `curl.exe` pierde las comillas del JSON. Ahí es más fácil `Invoke-RestMethod -Method Post <url> -ContentType 'application/json' -Body '{"tipo":"COMPRA","monto":500}'`. En bash o Git Bash:

```bash
curl -X POST localhost:8080/api/ordenes -H "Content-Type: application/json" -d '{"tipo":"COMPRA","monto":500}'
curl -X POST localhost:8080/api/ordenes/procesar
curl localhost:8080/api/cartera
curl -X POST localhost:8080/api/bot/iniciar -H "Content-Type: application/json" -d '{"segundosEntreCiclos":60}'
```

## Estructuras de datos a la vista

Son para la pantalla "Cómo funciona" del frontend.

### `GET /api/estructuras`

Muestra cómo están ahora las estructuras reales. Exige sesión. Leerlas no las cambia: la cola se lee rotándola y las pilas con una pila auxiliar.

- **De tu simulación:**
  - `cola`: las órdenes pendientes.
  - `pila`: el historial, con el más reciente primero.
  - `pilaDeshacer`: los ids que deshacería "Deshacer", del próximo al más viejo.
  - `lista`: cuántas órdenes hay en el registro.
- **Del servidor:**
  - `tablaHash`: la tabla de simulaciones de usuarios. Muestra solo cantidades, nunca ids.
  - `colaCircular`: el anillo de precios recientes, con el contenido de cada casilla tal como está en memoria.
  - `trie`: el trie de la búsqueda.
- Se muestran como máximo 10 elementos de cada estructura.

```json
{"cola":{"tamanio":2,"ordenes":[{"id":2,"tipo":"COMPRA","monto":20,"todo":false},…]},
 "pila":{"tamanio":4,"eventos":[{"tipo":"ORDEN_EJECUTADA","idOrden":1,"momento":1791433083120},…]},
 "pilaDeshacer":{"tamanio":3,"ids":[3,2,1]},
 "lista":{"tamanio":1},
 "tablaHash":{"capacidad":8,"tamanio":1,"factorCarga":0.125,"longitudes":[0,1,0,0,0,0,0,0]},
 "colaCircular":{"capacidad":120,"frente":0,"tamanio":1,"casillas":[83097.08,null,…]},
 "trie":{"palabras":222,"nodos":886}}
```

### `POST /api/estructuras/demo`

Corre operaciones sobre una estructura nueva, con el código real del backend, y devuelve cómo queda después de cada una. Es pública y no guarda nada.

```json
{"estructura":"avl","operaciones":[{"operacion":"insertar","valor":30},{"operacion":"insertar","valor":20},{"operacion":"insertar","valor":10}]}
```

| Estructura | Operaciones | Valores |
| --- | --- | --- |
| `cola` | `encolar`, `desencolar` | Enteros entre −9999 y 99999 |
| `pila` | `apilar`, `desapilar` | Enteros |
| `monticulo` | `insertar`, `extraer` (sale el menor) | Enteros |
| `avl` | `insertar`, `eliminar`, `buscar` | Enteros |
| `tabla-hash` | `poner`, `eliminar`, `buscar` (empieza con 4 cubetas) | Enteros |
| `cola-circular` | `agregar` (si está llena, pisa al más viejo), `desencolar` (8 casillas) | Enteros |
| `trie` | `insertar`, `eliminar`, `buscar` | Palabras de 1 a 12 letras, que se pasan a minúsculas y sin tildes |

- Se aceptan como máximo 30 operaciones.
- `desencolar`, `desapilar` y `extraer` no llevan `valor`.
- Cada paso devuelve `{operacion, valor, resultado, descripcion, complejidad, estado}`.
- `descripcion` explica lo que pasó, por ejemplo "Rotación simple a la derecha en 30." o "creció a 8 cubetas y reubicó todo (rehash)".
- `estado` es la foto para dibujar:
  - árbol AVL: nodos anidados con `clave`, `altura`, `izquierdo` y `derecho`;
  - montículo: el arreglo, nivel por nivel;
  - tabla hash: las claves de cada cubeta;
  - cola circular: las casillas en memoria y el frente;
  - trie: nodos anidados con `letra`, `fin` e `hijos`.
- Responde `400` si la estructura, la operación o un valor no son válidos.

## Tiempo real: `GET /api/stream`

Conexión que queda abierta y por la que el servidor envía eventos con **Server-Sent Events** (SSE): `Content-Type: text/event-stream`.

**Formato de cada evento:** una línea `event:` con el nombre, una línea `data:` con un JSON en una sola línea, y una línea vacía:

```
event: precio
data: {"simbolo":"BTCUSDT","precio":82724.02,"momento":1791434246201}

```

**Público o privado:** el stream no exige sesión. Sin sesión llega solo el precio. Con la cookie de sesión llegan además los eventos **de ese usuario** (sus órdenes, su cartera, su señal), en todos sus dispositivos conectados; nunca los de otra persona. Desde el navegador: `new EventSource(url, { withCredentials: true })`.

| Evento | Para quién | Cuándo llega | `data` |
| --- | --- | --- | --- |
| `precio` | Todos | Cada 5 segundos, mientras haya alguien conectado | `{simbolo, precio, momento}` |
| `orden` | El dueño | Cada vez que una orden cambia de estado: creada, procesando, ejecutada, rechazada, cancelada o deshecha | la orden completa, como en `/api/ordenes` |
| `cartera` | El dueño | Cuando cambian el saldo o el BTC, es decir, cuando se ejecuta una orden | igual que `/api/cartera` |
| `senal` | El dueño | Cuando cambia la decisión de la estrategia combinada. Lo publica el bot, así que solo llega con el bot en marcha; la primera decisión tras iniciarlo siempre se envía | la decisión `{tiempo, senal, precio, confianza, motivo}` |
| `alerta` | El dueño | Cuando se cumple una de sus alertas de precio | la alerta disparada `{id, tipo, precio, estado, creadaEn, disparadaEn, precioDisparo}` |

**Otros mensajes:**
- Al conectarse llega `retry: 5000` (si se corta, el navegador reintenta a los 5 s) y el comentario `: conectado`.
- Cada 15 segundos llega el comentario `: latido`, para que los proxies no cierren la conexión por inactividad. Las líneas que empiezan con `:` el navegador las ignora.
- El precio sale de la caché, así que puede repetirse durante `TTL_CACHE_SEGUNDOS`.

**Límite:** como máximo `MAX_STREAMS` conexiones simultáneas (por defecto 50). Si se supera, responde `503` con `{"error":"Demasiadas conexiones de tiempo real abiertas (máximo 50); intenta más tarde"}`.

**Desconexión:** cuando un cliente se va, el servidor lo nota al fallar la siguiente escritura (a más tardar en el próximo latido) y lo quita de la lista.

Probarlo:

```bash
curl -N localhost:8080/api/stream
```

Desde el panel (JavaScript):

```js
const fuente = new EventSource("https://tu-backend/api/stream", { withCredentials: true });
fuente.addEventListener("precio", e => console.log(JSON.parse(e.data).precio));
fuente.addEventListener("orden", e => console.log(JSON.parse(e.data)));
```

## Persistencia

La simulación de cada usuario (cartera, órdenes e historial) se guarda en la base de datos SQLite (`BASE_DATOS`, por defecto `<DATA_DIR>/bitcoinai.db`) **después de cada cambio**, y se carga la primera vez que el usuario la usa tras arrancar el servidor.

| Tabla | Contenido |
| --- | --- |
| `simulaciones` | Una fila por usuario: saldo inicial, saldo en USDT, BTC, costo de la posición, ganancia realizada, comisiones y próximo id de orden |
| `ordenes` | Cada orden con su lugar (`pendiente` en la cola o `registro`) y su posición dentro de él |
| `ordenes_creadas` | Ids en orden de creación (la Pila para seguir pudiendo deshacer) |
| `eventos_simulacion` | Historial del más viejo al más nuevo (los últimos 2000) |

- **Todo o nada:** cada guardado reemplaza la foto completa del usuario dentro de una transacción. Si el servidor muere a mitad, queda la anterior entera.
- **Mismo orden al recargar:** la Cola se reconstruye en el orden de llegada y las Pilas (historial e ids creados) quedan con el elemento más reciente arriba. Si el servidor se apagó mientras una orden se procesaba, esa orden vuelve al frente de la cola como pendiente.
- **Datos inválidos:** si la foto guardada de un usuario no se puede leer, se registra una advertencia y ese usuario empieza con una simulación limpia; los demás no se ven afectados.
- **Formato anterior:** los archivos JSON de la versión de un solo usuario (`AlmacenArchivos`) siguen en el código, pero el servidor ya no los usa.
- **Railway:** el disco de un contenedor de Railway **se borra en cada despliegue**. Para conservar usuarios y simulaciones hay que montar un volumen (por ejemplo en `/data`) y definir `DATA_DIR=/data`.

## Cuentas y seguridad

Registro con documento, inicio de sesión con correo y contraseña, verificación en dos pasos (Google Authenticator) y centro de seguridad. Más detalle técnico en [SEGURIDAD.md](SEGURIDAD.md).

**La sesión va en una cookie**, no en el cuerpo:

- **Atributos:** `HttpOnly` (el JavaScript de la página no la puede leer), `SameSite=Strict` (no se envía desde otros sitios) y `Path=/`.
- **Con `COOKIE_SEGURA=true`:** además lleva `Secure` y el nombre pasa a ser `__Host-sesion`.
- **Duración:** 12 horas como máximo; se cierra sola tras 2 horas sin uso.
- **Desde el frontend:** las peticiones deben enviarse con credenciales (`fetch(url, { credentials: "include" })`), y `ORIGEN_PERMITIDO` debe ser la URL exacta del frontend, nunca `*`.

**Errores propios de las cuentas** (siempre con `{"error": "..."}`):

| Código | Cuándo |
| --- | --- |
| 400 | Dato inválido. Incluye `campo` para marcar la casilla del formulario: `{"error":"Un celular colombiano tiene 10 dígitos y empieza por 3","campo":"telefono"}` |
| 401 | Correo o contraseña incorrectos (nunca se dice cuál de los dos), código incorrecto, o no hay sesión |
| 409 | El correo o el documento ya tienen cuenta, o la operación no aplica (por ejemplo, activar dos veces la verificación) |
| 429 | Demasiados intentos. Incluye `Retry-After` con los segundos de espera |

Las respuestas de `/api/cuentas/*` y `/api/sesion*` llevan `Cache-Control: no-store`.

### `POST /api/cuentas/registro`

```json
{"nombre":"Ana","apellido":"Pérez","correo":"ana@correo.co","tipoDocumento":"CC",
 "numeroDocumento":"1.023.456.789","telefono":"300 123 4567","contrasena":"Luna-Roja-2026"}
```

- **`tipoDocumento`:** `CC` (cédula de ciudadanía: de 5 a 10 dígitos) o `CE` (cédula de extranjería: de 5 a 12 letras o números). Se aceptan puntos, espacios y guiones.
- **`telefono`:** celular colombiano de 10 dígitos que empieza por 3, o cualquier número con indicativo (`+1…`, `+34…`). Se guarda como `+573001234567`.
- **`nombre` y `apellido`:** de 2 a 50 letras; se admiten tildes, ñ, espacios, apóstrofo y guion.
- **`contrasena`:**
  - De 10 a 128 caracteres.
  - Al menos 3 de estos 4: minúsculas, mayúsculas, números y símbolos.
  - No puede ser una contraseña común o predecible.
  - No puede contener el nombre, el correo ni el documento.
- **Campos desconocidos:** se rechazan con 400.
- **Límite:** 10 registros por hora desde una misma IP.

Responde `201` y deja la sesión abierta (`Set-Cookie`). El documento y el teléfono vuelven enmascarados:

```json
{"usuario":{"id":1,"nombre":"Ana","apellido":"Pérez","correo":"ana@correo.co","tipoDocumento":"CC",
 "documento":"******6789","telefono":"+57******4567","verificacionDosPasos":false,"creadoEn":1791604997952}}
```

### `POST /api/sesion`

Recibe `{"correo":"ana@correo.co","contrasena":"..."}`.

- **Sin verificación en dos pasos:** responde `{"segundoPaso": false, "usuario": {...}}` y abre la sesión.
- **Con verificación en dos pasos:** responde `{"segundoPaso": true}` y deja una cookie `desafio` de 5 minutos. Hay que enviar el código a `POST /api/sesion/codigo`.
- **Bloqueo:** tras 5 contraseñas equivocadas para un correo (o 20 desde una IP) en 15 minutos, responde `429` hasta que pase la ventana, aunque luego llegue la contraseña correcta.

### `POST /api/sesion/codigo`

Recibe `{"codigo":"123456"}`: el código de 6 dígitos de la app, o un código de respaldo (`ABCDE-FGHIJ`), que se gasta al usarlo.

- **Correcto:** responde como un inicio de sesión correcto.
- **Incorrecto:** `401`. Cada desafío admite 5 códigos equivocados.

### `DELETE /api/sesion`

Cierra la sesión de este dispositivo y borra la cookie. Responde `204`, aunque ya estuviera cerrada.

### `GET /api/cuentas/yo`

Devuelve `{"usuario": {...}}`, o `401` si no hay sesión. Sirve al frontend para saber si hay alguien conectado al cargar la página.

### Centro de seguridad (todo exige sesión)

| Método y ruta | Cuerpo | Respuesta |
| --- | --- | --- |
| `POST /api/cuentas/dos-pasos` | — | `{"secreto":"JBSW…","uri":"otpauth://totp/BitcoinAI:ana%40correo.co?…"}`. La `uri` se muestra como código QR para escanearlo con Google Authenticator; queda inactiva hasta confirmarla |
| `POST /api/cuentas/dos-pasos/confirmar` | `{"codigo":"123456"}` | `{"codigosRespaldo":["ABCDE-FGHIJ", …]}`: 10 códigos que se muestran una sola vez |
| `POST /api/cuentas/dos-pasos/desactivar` | `{"contrasena":"…","codigo":"123456"}` | `204` |
| `POST /api/cuentas/dos-pasos/codigos` | `{"codigo":"123456"}` | 10 códigos de respaldo nuevos; los anteriores dejan de servir |
| `GET /api/cuentas/sesiones` | — | `{"sesiones":[{"id","actual","ip","agente","creadaEn","ultimaActividad","expiraEn"}]}`, la más reciente primero |
| `DELETE /api/cuentas/sesiones/{id}` | — | `204`; `409` si no existe o ya estaba cerrada |
| `POST /api/cuentas/sesiones/cerrar-otras` | — | `{"cerradas": 2}` |
| `GET /api/cuentas/actividad?limite=50` | — | `{"eventos":[{"momento","tipo","descripcion","ip","detalle"}]}`, de 1 a 200 eventos, el más reciente primero |
| `POST /api/cuentas/contrasena` | `{"contrasenaActual":"…","contrasenaNueva":"…"}` | `204`. Cierra las demás sesiones. Si la nueva no cumple la política: `400` con `"campo":"contrasenaNueva"` |

Los códigos de 6 dígitos equivocados con la sesión abierta también se limitan: 5 cada 15 minutos.

## Límite de peticiones

Cada IP tiene un límite por minuto, en una ventana deslizante:

- **Rutas costosas** (`/api/ia/…`, `/api/estructuras/demo`, `/api/si-hubiera` y `/api/backtest`): 30 por minuto (`LIMITE_COSTOSAS`).
- **El resto de `/api`:** 600 por minuto (`LIMITE_GENERAL`). `/health` no cuenta.

Al pasarse, responde `429` con `Retry-After` y `{"error":"Demasiadas peticiones. Espera 12 s e intenta de nuevo."}`. La IP sale de `X-Forwarded-For` solo con `CONFIAR_PROXY=true`.

## Variables de entorno

Ninguna es obligatoria. La única secreta es `CLAVE_CIFRADO`.

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `PORT` | `8080` | Puerto HTTP. En Railway lo inyecta la plataforma; no lo definas a mano. |
| `BINANCE_BASE_URL` | `https://api.binance.com` | URL base de Binance. Cámbiala si Binance está bloqueado en tu región (por ejemplo `https://data-api.binance.vision`). |
| `ORIGEN_PERMITIDO` | `*` | Origen permitido para CORS; en producción, la URL del frontend. |
| `TTL_CACHE_SEGUNDOS` | `30` | Segundos que se guardan en caché el precio y las velas. `0` desactiva la caché. |
| `SIMBOLO` | `BTCUSDT` | Par de mercado que se consulta. |
| `MAX_STREAMS` | `50` | Conexiones simultáneas permitidas a `/api/stream` (entre 1 y 10 000). |
| `MAX_BOTS` | `20` | Bots simulados encendidos a la vez entre todos los usuarios (entre 1 y 1000). |
| `DATA_DIR` | `./data` | Carpeta donde se guarda la simulación. En Railway, apúntala a un volumen montado (por ejemplo `/data`); si no, se borra en cada despliegue. |
| `BASE_DATOS` | `<DATA_DIR>/bitcoinai.db` | Archivo SQLite con usuarios, sesiones y actividad. |
| `CLAVE_CIFRADO` | (se genera una local) | **Secreta.** 32 bytes en base64 para cifrar los datos personales. Si falta, se crea `<DATA_DIR>/clave-cifrado.key`. En producción defínela como secreto; si se pierde, los datos cifrados no se pueden recuperar. |
| `COOKIE_SEGURA` | `false` | `true` cuando el backend se sirve por HTTPS (Railway): cookie `Secure` con prefijo `__Host-` y HSTS. |
| `CONFIAR_PROXY` | `false` | `true` solo detrás de un proxy propio (Railway): la IP real se toma de `X-Forwarded-For`, para los límites de intentos y la actividad. |
| `LIMITE_GENERAL` | `600` | Peticiones a `/api` por minuto y por IP. |
| `LIMITE_COSTOSAS` | `30` | Peticiones por minuto y por IP a las rutas costosas (IA, demo, si-hubiera, backtest). |

Si una variable tiene un valor inválido (por ejemplo `PORT=abc`), el servidor no arranca y muestra un mensaje que explica el problema.
