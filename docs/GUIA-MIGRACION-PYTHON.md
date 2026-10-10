# Backend en Python: prompts por fases para Claude Code (migración)

## Por qué esta guía

El profesor aprobó las estructuras de datos, pero pidió el backend en **Python** (el frontend será TypeScript, en otro repo). Ya existe una versión completa en Java (fases 1 a 8). Esta guía la **migra** a Python con las mismas fases y en el mismo orden:

- **Se conserva:** el diseño, las estructuras, los algoritmos, las decisiones y el contrato de la API (`docs/API.md`), así el frontend no cambia.
- **Se reescribe:** el código, en Python idiomático.
- **Las pruebas como especificación:** cada prueba de Java se traduce a pytest con los mismos valores esperados.

## Decisiones de partida

| Tema | Elección | Motivo |
| --- | --- | --- |
| Lenguaje | Python 3.13 | Versión estable, soportada por todas las librerías y por la imagen Docker oficial |
| API | FastAPI + uvicorn | Rutas, validación y errores en poco código; documentación interactiva en `/docs` |
| Validación de entrada | pydantic (viene con FastAPI), solo en la capa `api` | La lógica del dominio no depende de FastAPI |
| Cliente HTTP | httpx | Tiempos de espera y reintentos simples; se prueba sin internet con `MockTransport` |
| JSON | Módulo `json` estándar | Python ya lo trae |
| Concurrencia | Lógica síncrona y protegida con `threading.Lock`; el bot corre en un hilo; los endpoints `def` corren en el grupo de hilos de FastAPI | Más simple de razonar y de probar que mezclar async en todo el dominio |
| Tiempo real | SSE con `StreamingResponse` | El servidor de FastAPI lo soporta sin dependencias extra |
| Persistencia | Archivos JSON con escritura atómica (`os.replace`) | Igual que en Java |
| Pruebas y calidad | pytest, ruff (estilo) y mypy en modo estricto (tipos) | Tipado completo, como pedía Java por naturaleza |
| Estructuras | Lista, ListaDoble, Cola y Pila a mano con nodos | Igual que en Java: es lo que evalúa el profesor |
| Paquete base | `bitcoinai`, en `src/bitcoinai` | Equivale a `com.bitcoinai.backend` |

**Regla de estructuras en Python:** dentro de la lógica del proyecto está prohibido usar `list`, `collections.deque`, `queue.Queue` o `heapq` como estructura. Se usan las propias. La única excepción es el borde de la API: FastAPI necesita una `list` para escribir el JSON, así que ahí (y solo ahí) se convierte.

**La versión Java como referencia:** queda guardada con la etiqueta `java-final`. Claude Code la consulta con `git show java-final:<ruta>`, por ejemplo `git show java-final:src/main/java/com/bitcoinai/backend/estructuras/ListaDoble.java`.

## Cómo usar los prompts

1. Abre el repo `Backend` en Claude Code y pega el Prompt 0. Crea la rama, quita el código Java y deja el esqueleto en Python con su `CLAUDE.md`.
2. Pega una fase por sesión, en orden. Cada fase empieza en su propia rama, creada desde la anterior (`python-fase-1-estructuras`, `python-fase-2-mercado`, …).
3. Al terminar cada fase, pide que se ejecuten `pytest`, `ruff check` y `mypy src`, y revisa que todo pase.
4. Haz el commit de cada fase tú mismo, con tu usuario, antes de pasar a la siguiente.
5. Si una fase queda a medias, pega el mismo prompt otra vez y añade "retoma donde quedaste".

## Prompt 0: esqueleto en Python

```text
Eres mi asistente de programación en el repo Backend de un proyecto universitario de Estructuras de Datos: un bot que analiza el mercado de Bitcoin y simula operaciones. El profesor pidió que el backend sea en Python (el frontend será TypeScript, en otro repo). En main ya existe una versión completa en Java (fases 1 a 8); vamos a migrarla a Python por fases.

Haz solo lo siguiente, sin adelantarte a otras fases:

1. Git: crea la etiqueta local java-final sobre el último commit de main (sin push) y trabaja en la rama python-fase-0-esqueleto, creada desde main.

2. Quita lo que es solo de Java: pom.xml, la carpeta src/ completa, Dockerfile y .dockerignore. Conserva docs/ (API.md es el contrato y no cambia), README.md (se reescribe en la Fase 8) y .github/. El código Java sigue disponible con git show java-final:<ruta>.

3. Crea el proyecto Python:
   - Entorno virtual .venv con Python 3.13 (en Windows: py -3.13 -m venv .venv).
   - pyproject.toml: nombre bitcoinai-backend, requires-python >= 3.13, código en src/bitcoinai, dependencias fastapi, uvicorn y httpx, y un extra "dev" con pytest, ruff y mypy. Antes de fijar versiones revisa las actuales con pip index versions y dime cuáles quedaron.
   - Configura pytest (pruebas en tests/, marca "manual" excluida por defecto), ruff (estilo y orden de imports, largo de línea 120) y mypy en modo strict.

4. Paquetes bajo src/bitcoinai: estructuras, modelo, mercado, indicadores, estrategia, simulacion, api y persistencia, cada uno con su __init__.py. Un __main__.py que por ahora solo imprima "Backend iniciado", y una prueba trivial de eso.

5. .gitignore: quita lo de Maven y agrega .venv/, __pycache__/, *.pyc, .pytest_cache/, .mypy_cache/, .ruff_cache/, data/ y .env.

6. CI: cambia .github/workflows/ci.yml para que en cada push y pull request instale Python 3.13 y ejecute ruff check, mypy src y pytest.

7. Reescribe el CLAUDE.md en español y breve, con:
   - Objetivo: el mismo (velas de BTCUSDT de Binance, indicadores, señales, simulación de operaciones y API HTTP; no opera con dinero real).
   - Reglas: Python 3.13; FastAPI + uvicorn para la API; httpx para Binance; json estándar; pydantic solo en el paquete api; tipado completo con mypy strict; todo simulado, sin cuentas reales ni claves de exchange.
   - Estructuras de datos: Lista, ListaDoble, Cola y Pila a mano con nodos enlazados; prohibido usar list, collections.deque, queue.Queue o heapq como estructura en la lógica del proyecto (solo en el borde de la API se convierte a list para escribir el JSON); nombres de clases y métodos en español, en snake_case.
   - Migración: la referencia es la versión Java (git show java-final:<ruta>) y docs/; se porta el comportamiento y las pruebas con los mismos valores esperados, escribiendo Python idiomático; el contrato docs/API.md no cambia.
   - Paquetes, comandos (crear y activar el venv, pip install -e ".[dev]", pytest, ruff check, mypy src, ejecutar con python -m bitcoinai) y convenciones (cada módulo público con pruebas; docstrings en español con la complejidad de cada operación de las estructuras; no hacer commit ni push salvo que yo lo pida).
   - Fases: las 8 fases (estructuras, mercado, API, indicadores, señales y backtesting, simulación, tiempo real y persistencia, Docker y Railway) con una casilla [ ] cada una.

8. Verifica: pip install -e ".[dev]", pytest, ruff check y mypy src. Muéstrame los resultados, las versiones instaladas y los archivos creados.
```

**Listo cuando:** en la rama `python-fase-0-esqueleto` ya no queda código Java, y `pytest`, `ruff check` y `mypy src` pasan.

## Fase 1: estructuras de datos

Es lo que el profesor ya aprobó. Se porta tal cual, con el estilo de Python. Incluye desde el inicio las dos operaciones de la lista doble que en Java llegaron en la Fase 7 (agregar devolviendo el nodo y eliminar por nodo).

```text
Lee el CLAUDE.md. Vamos a implementar la Fase 1 de la migración: las estructuras de datos, en el paquete bitcoinai.estructuras. Porta la versión Java (git show java-final:src/main/java/com/bitcoinai/backend/estructuras/...) y sus pruebas.

1. NodoSimple y NodoDoble genéricos (Generic[T]), con __slots__. Los enlaces se modifican solo desde las estructuras del paquete.

2. Lista[T] (simplemente enlazada con cabeza y cola): agregar, agregar_inicio, insertar_ordenado(valor, clave) estable con iguales, obtener(indice), eliminar(indice), buscar(condicion) que devuelve el índice o -1, primero, ultimo, tamanio, esta_vacia, vaciar.

3. ListaDoble[T] (doblemente enlazada con cabeza y cola): agregar_inicio, agregar_final, agregar_final_nodo (devuelve el nodo), eliminar_nodo(nodo) en O(1) que devuelve False si el nodo no pertenece a la lista o ya se quitó (también tras vaciar), insertar(indice, valor), obtener(indice) desde el extremo más cercano, eliminar_primero, eliminar_ultimo, eliminar(indice), primero, ultimo, tamanio, esta_vacia, vaciar, conservar_ultimos(n), iterador_adelante() e iterador_atras() con iteradores propios.

4. Cola[T] (FIFO con frente y final) y Pila[T] (LIFO con tope): encolar, desencolar, ver_frente / apilar, desapilar, ver_tope, más tamanio, esta_vacia y vaciar. Todo O(1).

5. Lista y ListaDoble implementan __iter__ (for) y __len__; Cola y Pila implementan solo __len__.

6. Excepciones propias: EstructuraVaciaError e IndiceFueraDeRangoError ("Índice 5 fuera de rango para tamaño 3"). Nunca se devuelve None en esos casos.

Reglas:
- Sin list, deque ni otras colecciones dentro de las estructuras.
- Docstring en español en cada método público con su complejidad ("Complejidad: O(1)").
- Pruebas pytest con los mismos casos que en Java: vacía, un elemento, extremos, índices inválidos, orden correcto, el recorrido hacia atrás inverso al de adelante tras varias operaciones, y eliminar_nodo (medio, extremos, dos veces, nodo ajeno, tras vaciar). Al menos 8 pruebas por clase.
- Actualiza docs/ESTRUCTURAS.md con los nombres de Python (la tabla de complejidades y el uso de cada estructura en el proyecto no cambian).
- Marca la Fase 1 en el CLAUDE.md.

Al terminar ejecuta pytest, ruff check y mypy src y muéstrame el resultado.
```

**Listo cuando:** `pytest`, `ruff check` y `mypy src` pasan, y `docs/ESTRUCTURAS.md` tiene los nombres de Python.

## Fase 2: datos reales de Bitcoin

```text
Lee el CLAUDE.md. Vamos a implementar la Fase 2 de la migración: modelo y cliente de mercado. Porta la versión Java (git show java-final:src/main/java/com/bitcoinai/backend/modelo/... y .../mercado/...) y sus pruebas. Usa las estructuras de la Fase 1.

1. Paquete modelo: Vela como dataclass inmutable (frozen, slots) con tiempo_apertura, apertura, maximo, minimo, cierre, volumen y tiempo_cierre; e Intervalo como Enum con 1m, 5m, 15m, 1h, 4h y 1d (código de Binance y milisegundos) y desde_codigo(texto).

2. Paquete mercado:
   - FuenteDeMercado (Protocol) con obtener_velas(simbolo, intervalo, cantidad) -> ListaDoble[Vela] ordenada de la más antigua a la más reciente, y obtener_precio_actual(simbolo) -> float.
   - ClienteBinance con httpx: GET /api/v3/klines y /api/v3/ticker/price; más de 1000 velas se piden hacia atrás con endTime, juntando con iterador_atras y agregar_inicio sin duplicados (pide una vela extra al paginar, como en Java).
   - URL base desde BINANCE_BASE_URL (por defecto https://api.binance.com), tiempos de espera de conexión y respuesta, un reintento ante fallos de red o 5xx (los 4xx no se reintentan) y MercadoError con mensaje claro que incluya el "msg" de Binance.
   - Símbolo en mayúsculas y validado (solo letras y dígitos).
   - CacheMercado que envuelve cualquier fuente, con TTL configurable y reloj inyectable; devuelve copias y no guarda errores.
   - ValidadorVelas: ordenadas, sin duplicados, precios positivos y finitos, máximo >= mínimo, apertura y cierre dentro del rango, volumen no negativo, cierre no anterior a la apertura. Si falla, MercadoError con la posición y el motivo.
   - velas_cerradas(velas, ahora): quita del final las velas que todavía no cerraron.

3. Pruebas sin internet: una respuesta de klines escrita a mano, el cliente contra httpx.MockTransport (una petición, paginación, solapamiento, historial corto, 4xx con msg, 5xx con reintento, tiempo agotado, sin conexión), una FuenteFalsa reutilizable (en tests/) para la caché, y la validación.

4. Una prueba manual con la marca "manual" (no corre con pytest normal) que descargue 10 velas reales de BTCUSDT 1d. Documenta en el CLAUDE.md cómo correrla (pytest -m manual).

Marca la Fase 2 en el CLAUDE.md. Al terminar ejecuta pytest, ruff check y mypy src y muéstrame el resultado.
```

**Listo cuando:** pasan las tres verificaciones y, al correr `pytest -m manual`, aparecen velas reales de Bitcoin.

## Fase 3: API HTTP

```text
Lee el CLAUDE.md. Vamos a implementar la Fase 3 de la migración: la API HTTP con FastAPI, en el paquete api. El contrato es docs/API.md y no cambia: mismas rutas, mismos parámetros, mismos códigos y la misma forma del JSON. Porta también el comportamiento de la versión Java (git show java-final:src/main/java/com/bitcoinai/backend/api/...).

1. Configuracion (dataclass) desde variables de entorno con valores por defecto: PORT (8080), BINANCE_BASE_URL, ORIGEN_PERMITIDO (*), TTL_CACHE_SEGUNDOS (30) y SIMBOLO (BTCUSDT). Valores inválidos → error claro al arrancar.

2. crear_app(...) -> FastAPI, que recibe sus dependencias (configuración, fuente de mercado), para que las pruebas usen una FuenteFalsa. python -m bitcoinai arranca uvicorn en 0.0.0.0 y el puerto PORT.

3. Errores siempre en JSON con la forma {"error": "mensaje"}: 404 si la ruta no existe, 405 si el método no corresponde (con Allow), 400 con el motivo si un parámetro es inválido (convierte las validaciones de FastAPI, que por defecto dan 422, a 400 con un mensaje en español), 502 "Fuente de mercado no disponible" si falla Binance y 500 "Error interno del servidor" sin detalles ni trazas. Una barra final en la ruta se ignora.

4. CORS con ORIGEN_PERMITIDO (y respuesta a OPTIONS) y un registro de cada petición en una línea: método, ruta, código y milisegundos.

5. Endpoints: GET /health (sin consultar Binance), GET /api/precio y GET /api/velas?intervalo=1d&cantidad=200 (intervalo del enum y cantidad entre 1 y 1000). La lógica se queda en los paquetes del dominio; los endpoints solo traducen.

6. Pruebas con TestClient y una FuenteFalsa: respuestas correctas, parámetros inválidos, ruta inexistente, método no permitido, CORS, 502 y 500.

7. Actualiza docs/API.md solo para agregar cómo arrancar el servidor en Python y que FastAPI publica la documentación interactiva en /docs.

Marca la Fase 3 en el CLAUDE.md. Al terminar ejecuta pytest, ruff check y mypy src, y explica cómo arrancar el servidor a mano y probarlo con curl.
```

**Listo cuando:** el servidor arranca en tu computador y `curl "localhost:8080/api/velas?intervalo=1d&cantidad=5"` devuelve velas reales con la misma forma que en Java.

## Fase 4: indicadores técnicos

```text
Lee el CLAUDE.md. Vamos a implementar la Fase 4 de la migración: indicadores técnicos, en el paquete indicadores. Porta la versión Java (git show java-final:src/main/java/com/bitcoinai/backend/indicadores/...) y sus pruebas, con los mismos valores calculados a mano.

1. PuntoIndicador (dataclass inmutable: tiempo, valor) y el Protocol Indicador con nombre(), parametros(), calcular(velas) -> ListaDoble[PuntoIndicador] y calcular_series(velas) -> dict de series con nombre.
2. Series: cierres(velas), ultimos(lista, n) con recorrido hacia atrás (explica por qué en un comentario) y ema(serie, periodo).
3. Indicadores: Sma (ventana ListaDoble con conservar_ultimos y suma acumulada, O(n)), Ema (inicializada con la SMA; periodo 1 = precio), Rsi (suavizado de Wilder; serie plana = 50, siempre sube = 100, siempre baja = 0), Macd (macd, señal e histograma, alineados con Series.ultimos), BandasBollinger (desviación poblacional, cierres desplazados por el primero para no perder precisión), Volatilidad (desviación muestral de los retornos logarítmicos, sin anualizar) y MaximaCaida (un solo recorrido; de velas o de puntos).
4. FabricaIndicadores.crear(nombre, parametros) con sma, ema, rsi, macd, bollinger y volatilidad; periodos entre 2 y 1000; un periodo mayor que las velas da lista vacía, no error.
5. Docstring con la fórmula y la complejidad de cada indicador.
6. API: GET /api/indicadores con la misma respuesta que en Java (indicador, parametros, series, maximaCaida, cantidad, velas) y 400 si algo es inválido, validando antes de consultar Binance.

Pruebas con los mismos casos de Java (SMA de [1,2,3,4,5] con periodo 3 = [2,3,4], RSI de 1,2,1,2,3 con periodo 2 = 50, 75 y 87,5, MACD de 1..6 con 2/3/2, Bollinger de 1,3,5, volatilidad de 1, e, e³, etc.), más series vacías y de un elemento.

Marca la Fase 4 en el CLAUDE.md. Al terminar ejecuta pytest, ruff check y mypy src.
```

**Listo cuando:** pasan las tres verificaciones y `/api/indicadores?indicador=rsi` devuelve la serie del RSI con velas reales.

## Fase 5: señales y backtesting

```text
Lee el CLAUDE.md. Vamos a implementar la Fase 5 de la migración: señales y backtesting, en el paquete estrategia. Porta la versión Java (git show java-final:src/main/java/com/bitcoinai/backend/estrategia/...) y sus pruebas.

1. Senal y Direccion (Enum), Decision (dataclass inmutable con confianza entre 0 y 1 y motivo obligatorio), el Protocol Estrategia (nombre, parametros, velas_minimas, evaluar, indicadores_actuales, justificacion).
2. CruceDeMedias (20/50), EstrategiaRsi (14, 30/70, compra al salir de sobreventa), EstrategiaMacd (12/26/9) y EstrategiaCombinada (votación ponderada; empates a favor de MANTENER; MANTENER neutral con confianza 0,25). Señales por evento, con tolerancia numérica para no detectar cruces por ruido.
3. Pronostico con dirección, confianza, justificación, indicadores y el aviso fijo "Resultado de pruebas con datos históricos; no es asesoría financiera ni garantiza ganancias".
4. Backtester: recorre la ListaDoble agregando una vela por vuelta (nunca mira el futuro), ejecuta en la apertura de la vela siguiente, comisión (0,1 %), solo largos, cierre forzado al final, decisiones en una Pila y operaciones en una Lista; ResultadoBacktest con las mismas métricas que en Java (incluida la curva de capital y comprar y mantener).
5. ValidacionEntrenamientoPrueba 70/30 y FabricaEstrategias (crear y candidatos), con las mismas combinaciones de parámetros.
6. API: GET /api/senal y GET /api/backtest con la misma respuesta que en Java, descartando la vela que todavía no cerró.

Pruebas: las mismas que en Java, incluidas las series sintéticas (V, V invertida y lateral, con la compra del RSI en la vela 63), la estrategia espía que comprueba que no se mira el futuro, la comisión calculada a mano, comprar y mantener y la división 70/30 sin mezclar datos.

Marca la Fase 5 en el CLAUDE.md. Al terminar ejecuta pytest, ruff check y mypy src.
```

**Listo cuando:** pasan las tres verificaciones y `/api/backtest` devuelve métricas con datos reales, incluida la comparación con comprar y mantener.

## Fase 6: simulación de operaciones

```text
Lee el CLAUDE.md. Vamos a implementar la Fase 6 de la migración: simulación de operaciones (paper trading), en el paquete simulacion. Porta la versión Java (git show java-final:src/main/java/com/bitcoinai/backend/simulacion/... y api/RutasSimulacion.java) y sus pruebas. Nunca se conecta a una cuenta real ni usa claves de exchange.

1. TipoOrden, EstadoOrden y TipoEvento (Enum); Orden y Evento como dataclasses inmutables (los cambios de estado crean una orden nueva con dataclasses.replace).
2. Cartera (10 000 USDT por defecto; costo promedio con comisiones; ganancia realizada y no realizada; OperacionRechazadaError con el motivo).
3. LibroDeOrdenes con Cola de pendientes, Lista de registro, Pila de eventos y Pila de ids creados (para deshacer, repetible). Dos threading.Lock: uno para las estructuras (nunca tomado durante la consulta del precio) y otro para procesar de a una en orden FIFO; estado PROCESANDO visible; si falla el precio, la orden vuelve al frente. cancelar(id) reconstruye la cola en O(n); historial(limite) lee la pila sin perderla en O(k).
4. BotSimulado en un hilo propio que se puede iniciar y detener (ConfiguracionBot validada: segundos entre ciclos, intervalo, velas, riesgo 20 %, stop-loss 5 % y take-profit 10 %), con prioridad del stop-loss y del take-profit, ventas de todo el BTC y procesamiento de la cola al final de cada ciclo. Los errores del ciclo quedan en el estado y en el historial.
5. API con FastAPI, igual que en Java: POST /api/ordenes (cuerpo validado con pydantic, 400 con el motivo), GET /api/ordenes?estado=, GET y DELETE /api/ordenes/{id}, POST /api/ordenes/procesar, POST /api/ordenes/deshacer, GET /api/cartera, GET /api/historial?limite=, POST /api/bot/iniciar (configuración opcional), POST /api/bot/detener y GET /api/bot/estado. 404 si la orden no existe y 409 si el estado no lo permite.

Pruebas: las mismas que en Java (FIFO, compra y venta con comisión, rechazos, cancelar del medio, deshacer, PROCESANDO con una fuente lenta, varios hilos creando a la vez sin perder órdenes, bot con FuenteFalsa y estrategia falsa, stop-loss y take-profit, endpoints).

Marca la Fase 6 en el CLAUDE.md. Al terminar ejecuta pytest, ruff check y mypy src.
```

**Listo cuando:** pasan las tres verificaciones y, con el servidor arrancado, puedes crear una orden, procesarla y ver el cambio en `/api/cartera`.

## Fase 7: tiempo real y persistencia

```text
Lee el CLAUDE.md. Vamos a implementar la Fase 7 de la migración: tiempo real con SSE y persistencia en archivos. Porta la versión Java (git show java-final:src/main/java/com/bitcoinai/backend/api/Publicador.java, Suscriptor.java, ManejadorStream.java y el paquete persistencia) y sus pruebas.

A. Tiempo real:
1. GET /api/stream con StreamingResponse (text/event-stream): eventos precio (cada 5 s), orden, cartera y senal, cada uno con un JSON en la línea data; retry: 5000 y ": conectado" al inicio; latido ": latido" cada 15 s.
2. Los suscriptores van en una ListaDoble; cada uno guarda su nodo y se elimina con eliminar_nodo en O(1) al desconectarse (documéntalo en el código). Cada suscriptor tiene su buzón con una Cola propia (no queue.Queue) y un aviso para el generador asíncrono, porque los eventos llegan desde otros hilos.
3. MAX_STREAMS (por defecto 50); si se supera, 503 en JSON.
4. El libro de órdenes y el bot publican mediante el Protocol PublicadorEventos, sin depender de la capa HTTP.

B. Persistencia (paquete persistencia):
1. DATA_DIR (por defecto ./data) con cartera.json, ordenes.json e historial.json en el mismo formato que en Java; guarda después de cada cambio con escritura atómica (temporal + os.replace) y carga al iniciar.
2. Reconstruye el mismo orden: la Cola con el orden de llegada y las Pilas con lo más reciente arriba; los últimos 2000 eventos.
3. Un archivo dañado o faltante no impide arrancar: se aparta como .danado-<momento>, se registra una advertencia y se empieza limpio (cartera y órdenes juntas, historial aparte).
4. Documenta que el disco de Railway se borra en cada despliegue salvo que se monte un volumen y DATA_DIR apunte a él.

Pruebas: ida y vuelta con el mismo orden de la cola y de la pila, archivo dañado, un cliente HTTP real que reciba eventos del stream, una desconexión que quite al suscriptor de la lista y el límite de conexiones. Agrega MAX_STREAMS y DATA_DIR a la configuración.

Actualiza docs/API.md si algo cambió. Marca la Fase 7 en el CLAUDE.md. Al terminar ejecuta pytest, ruff check y mypy src.
```

**Listo cuando:** pasan las tres verificaciones; con `curl -N localhost:8080/api/stream` ves llegar precios, y al reiniciar el servidor la cartera y las órdenes siguen ahí.

## Fase 8: Docker y Railway

```text
Lee el CLAUDE.md. Vamos a implementar la Fase 8 de la migración: contenedor Docker listo para Railway.

1. Dockerfile de dos etapas: construcción con python:3.13-slim que instala las dependencias en un entorno virtual (copiando primero pyproject.toml para aprovechar la caché de capas) y ejecución con python:3.13-slim que copia solo el entorno y el código, crea y usa un usuario sin privilegios y arranca uvicorn en 0.0.0.0 y $PORT (8080 si no existe). No fijes el puerto en el Dockerfile.
2. .dockerignore (.venv/, .git/, data/, __pycache__/, cachés, *.md salvo README.md).
3. Si Binance responde HTTP 451, MercadoError con "Binance no está disponible desde esta región; cambia la región del servicio o la URL base", registrado en el log; /health no depende de Binance.
4. El CI ya ejecuta ruff, mypy y pytest; revisa que siga funcionando.
5. Reescribe el README.md para Python: qué es, cómo instalar y ejecutar en local, la tabla de variables (PORT, BINANCE_BASE_URL, ORIGEN_PERMITIDO, TTL_CACHE_SEGUNDOS, SIMBOLO, DATA_DIR, MAX_STREAMS), docker build y docker run, los pasos en Railway (incluido RAILWAY_RUN_UID=0 si se monta un volumen con un usuario sin privilegios), el mapa de endpoints y la sección "Estructuras de datos".
6. Verifica lo que puedas: pytest, ruff check y mypy src; si Docker está disponible, docker build y docker run con una prueba de /health. Si no está disponible, dilo y no inventes el resultado.

Marca la Fase 8 en el CLAUDE.md. Muéstrame los archivos creados y el resultado de las verificaciones.
```

**Pasos en Railway (los haces tú):** son los mismos que con Java.

1. Despliega desde el repo `Backend`.
2. Define `ORIGEN_PERMITIDO`, y `DATA_DIR=/data` con `RAILWAY_RUN_UID=0` si montas un volumen en `/data`.
3. Genera un dominio público y pon `/health` como ruta del healthcheck.
4. Si aparece el error de región, cambia la región del servicio.

**Listo cuando:** `https://tu-dominio/health` responde `{"estado":"ok"}` y `/api/velas?intervalo=1d&cantidad=5` devuelve velas reales.
