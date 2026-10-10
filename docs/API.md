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
| 502 | La fuente de mercado (Binance) falló: `{"error":"Fuente de mercado no disponible"}` |
| 500 | Error inesperado: `{"error":"Error interno del servidor"}`, sin detalles ni trazas |

- **CORS:** todas las respuestas llevan `Access-Control-Allow-Origin` con el valor de `ORIGEN_PERMITIDO`. Las peticiones `OPTIONS` (preflight) reciben `204` sin cuerpo.
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

## Simulación de operaciones (paper trading)

> **Todo es simulado:** no hay dinero real, ni conexión a una cuenta de exchange, ni claves de API. El único dato externo es el precio público de Binance, que se usa para ejecutar las órdenes simuladas.

**Cómo funciona:**
- **Cartera:** empieza con 10 000 USDT y 0 BTC. Cada compra y cada venta paga una comisión de 0,1 %.
- **Cola de pendientes:** cada orden nueva espera en una **Cola** y se ejecuta en orden de llegada (FIFO), al precio actual.
- **Registro:** las órdenes terminadas (ejecutadas, canceladas o rechazadas) quedan en una **Lista**.
- **Historial:** cada evento se apila en una **Pila**, con el más reciente arriba.
- **Quién ejecuta:** con el bot detenido, las órdenes se ejecutan con `POST /api/ordenes/procesar`. Con el bot en marcha, al final de cada ciclo procesa la cola entera, incluidas las órdenes manuales.
- **Persistencia:** el estado se guarda en `DATA_DIR` después de cada cambio y se recupera al reiniciar (ver [Persistencia](#persistencia)).

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
| 409 | El estado no lo permite: cancelar algo ya ejecutado, procesar con la cola vacía, iniciar el bot dos veces |
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

### Bot simulado

| Método y ruta | Qué hace |
| --- | --- |
| `POST /api/bot/iniciar` | Lo pone en marcha; el primer ciclo es inmediato. Cuerpo opcional (abajo). 409 si ya estaba en marcha |
| `POST /api/bot/detener` | Lo detiene (si ya estaba detenido, no hace nada) |
| `GET /api/bot/estado` | `{activo, estrategia, configuracion, ciclos, ultimoCiclo, ultimaDecision, ultimoError}` |

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

## Tiempo real: `GET /api/stream`

Conexión que queda abierta y por la que el servidor envía eventos con **Server-Sent Events** (SSE): `Content-Type: text/event-stream`.

**Formato de cada evento:** una línea `event:` con el nombre, una línea `data:` con un JSON en una sola línea, y una línea vacía:

```
event: precio
data: {"simbolo":"BTCUSDT","precio":82724.02,"momento":1791434246201}

```

| Evento | Cuándo llega | `data` |
| --- | --- | --- |
| `precio` | Cada 5 segundos, mientras haya alguien conectado | `{simbolo, precio, momento}` |
| `orden` | Cada vez que una orden cambia de estado: creada, procesando, ejecutada, rechazada, cancelada o deshecha | la orden completa, como en `/api/ordenes` |
| `cartera` | Cuando cambian el saldo o el BTC, es decir, cuando se ejecuta una orden | igual que `/api/cartera` |
| `senal` | Cuando cambia la decisión de la estrategia combinada. Lo publica el bot, así que solo llega con el bot en marcha; la primera decisión tras iniciarlo siempre se envía | la decisión `{tiempo, senal, precio, confianza, motivo}` |

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
const fuente = new EventSource("https://tu-backend/api/stream");
fuente.addEventListener("precio", e => console.log(JSON.parse(e.data).precio));
fuente.addEventListener("orden", e => console.log(JSON.parse(e.data)));
```

## Persistencia

La simulación (cartera, órdenes e historial) se guarda en archivos JSON dentro de `DATA_DIR` (por defecto `./data`) **después de cada cambio**, y se carga al arrancar el servidor.

| Archivo | Contenido |
| --- | --- |
| `cartera.json` | Saldo inicial, saldo en USDT, BTC, costo de la posición, ganancia realizada y comisiones |
| `ordenes.json` | Cola de pendientes en orden de llegada, registro de órdenes terminadas, ids en orden de creación (para seguir pudiendo deshacer) y próximo id |
| `historial.json` | Eventos del más viejo al más nuevo (los últimos 2000) |

- **Escritura atómica:** cada archivo se escribe primero en un `.tmp` y luego se mueve sobre el definitivo. Si el servidor muere a mitad de una escritura, queda el archivo anterior completo, nunca uno a medias.
- **Mismo orden al recargar:** la Cola se reconstruye en el orden de llegada y las Pilas (historial e ids creados) quedan con el elemento más reciente arriba. Si el servidor se apagó mientras una orden se procesaba, esa orden vuelve al frente de la cola como pendiente.
- **Archivos dañados:**
  - Si un archivo no se puede leer, el servidor arranca igual: se renombra a `*.danado-<momento>` para poder revisarlo, se registra una advertencia y se empieza con estado limpio.
  - `cartera.json` y `ordenes.json` se cargan juntos: si uno falla o falta, no se usa ninguno, para no mezclar una cartera con órdenes que no le corresponden.
  - El historial se carga aparte.
- **Railway:** el disco de un contenedor de Railway **se borra en cada despliegue**. Para conservar la simulación hay que montar un volumen (por ejemplo en `/data`) y definir `DATA_DIR=/data`. Sin volumen, cada despliegue empieza con 10 000 USDT nuevos.

## Variables de entorno

Ninguna es obligatoria y ninguna es secreta.

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `PORT` | `8080` | Puerto HTTP. En Railway lo inyecta la plataforma; no lo definas a mano. |
| `BINANCE_BASE_URL` | `https://api.binance.com` | URL base de Binance. Cámbiala si Binance está bloqueado en tu región (por ejemplo `https://data-api.binance.vision`). |
| `ORIGEN_PERMITIDO` | `*` | Origen permitido para CORS; en producción, la URL del frontend. |
| `TTL_CACHE_SEGUNDOS` | `30` | Segundos que se guardan en caché el precio y las velas. `0` desactiva la caché. |
| `SIMBOLO` | `BTCUSDT` | Par de mercado que se consulta. |
| `MAX_STREAMS` | `50` | Conexiones simultáneas permitidas a `/api/stream` (entre 1 y 10 000). |
| `DATA_DIR` | `./data` | Carpeta donde se guarda la simulación. En Railway, apúntala a un volumen montado (por ejemplo `/data`); si no, se borra en cada despliegue. |

Si una variable tiene un valor inválido (por ejemplo `PORT=abc`), el servidor no arranca y muestra un mensaje que explica el problema.
