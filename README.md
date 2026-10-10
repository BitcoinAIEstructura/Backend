# Backend del bot de Bitcoin

Backend de un proyecto universitario de **Estructuras de Datos**: un bot que analiza el mercado de Bitcoin (BTCUSDT) y simula operaciones.

- Obtiene velas reales de la API pública de Binance.
- Calcula indicadores técnicos (SMA, EMA, RSI, MACD, Bollinger, volatilidad).
- Genera señales con varias estrategias, las prueba con datos históricos (backtesting con validación entrenamiento/prueba) y simula operaciones: cada usuario tiene su propia cartera ficticia, sus órdenes y su bot.
- Expone todo por HTTP, con eventos en tiempo real (SSE).
- Cuentas de usuario seguras: registro con cédula (CC o CE), contraseñas con Argon2id, datos personales cifrados, verificación en dos pasos con Google Authenticator y centro de seguridad. Ver [docs/SEGURIDAD.md](docs/SEGURIDAD.md).

> **Todo es simulado.** No opera con dinero real, no se conecta a ninguna cuenta de exchange y no usa claves de API. Los resultados no son asesoría financiera ni garantizan ganancias.

Está escrito en **Python 3.13 con FastAPI**. El frontend (TypeScript) está en otro repositorio.
- **HTTP:** el servidor es FastAPI sobre uvicorn y el cliente de Binance usa httpx.
- **JSON:** el módulo estándar `json`.
- **Estructuras:** listas, colas y pilas implementadas a mano con nodos enlazados (ver más abajo).
- **Base de datos:** SQLite (módulo estándar `sqlite3`) para usuarios, sesiones y actividad.
- **Dependencias:** FastAPI, uvicorn, httpx, argon2-cffi y cryptography; para desarrollar, pytest, ruff y mypy.

La primera versión del proyecto estaba en Java 21; quedó guardada en la etiqueta `java-final`.

## Instalar y ejecutar localmente

Requisito: Python 3.13.

Crear el entorno virtual (una vez):

```bash
py -3.13 -m venv .venv
```

En Linux o macOS es `python3.13 -m venv .venv`. Activarlo: `.venv\Scripts\activate` en Windows, `source .venv/bin/activate` en Linux o macOS. Después:

```bash
pip install -e ".[dev]"
```

```bash
pytest
```

```bash
python -m bitcoinai
```

El servidor queda en `http://localhost:8080` (Ctrl+C lo apaga). La documentación interactiva de FastAPI está en `http://localhost:8080/docs`. Para probarlo:

```bash
curl localhost:8080/health
curl "localhost:8080/api/velas?intervalo=1d&cantidad=5"
curl -N localhost:8080/api/stream
```

En PowerShell usa `curl.exe` en lugar de `curl`. Para los POST con cuerpo JSON es más cómodo `Invoke-RestMethod`; ver [docs/API.md](docs/API.md).

Revisiones que también corre el CI:

```bash
ruff check
```

```bash
mypy src
```

Hay una prueba manual que descarga velas reales de Binance (necesita internet); no corre con `pytest` a secas:

```bash
pytest -m manual -s
```

## Variables de entorno

Ninguna es obligatoria. La única secreta es `CLAVE_CIFRADO`. Hay un ejemplo completo en [.env.example](.env.example).

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `PORT` | `8080` | Puerto HTTP. Railway lo define solo; no lo pongas a mano allí. |
| `BINANCE_BASE_URL` | `https://api.binance.com` | URL base de Binance. Cámbiala si Binance está bloqueado en la región (por ejemplo `https://data-api.binance.vision`). |
| `ORIGEN_PERMITIDO` | `*` | Origen permitido para CORS; en producción, la URL del frontend. |
| `TTL_CACHE_SEGUNDOS` | `30` | Segundos que se guardan en caché el precio y las velas (`0` la desactiva). |
| `SIMBOLO` | `BTCUSDT` | Par de mercado. |
| `DATA_DIR` | `./data` | Carpeta donde se guarda la simulación (cartera, órdenes e historial). |
| `MAX_STREAMS` | `50` | Conexiones simultáneas permitidas a `/api/stream` (entre 1 y 10 000). |
| `MAX_BOTS` | `20` | Bots simulados encendidos a la vez entre todos los usuarios. |
| `BASE_DATOS` | `<DATA_DIR>/bitcoinai.db` | Archivo SQLite de usuarios, sesiones y actividad. |
| `CLAVE_CIFRADO` | (se genera una local) | **Secreta.** 32 bytes en base64 para cifrar los datos personales. Si falta, se crea `data/clave-cifrado.key`. |
| `COOKIE_SEGURA` | `false` | `true` con HTTPS: cookie `Secure` con prefijo `__Host-` y HSTS. |
| `CONFIAR_PROXY` | `false` | `true` detrás del proxy de Railway, para leer la IP real. |

Si una variable tiene un valor inválido, el servidor no arranca y explica cuál es el problema.

## Docker

La imagen se construye en dos etapas, las dos sobre `python:3.13-slim`:
- **Construcción:** instala las dependencias y el proyecto en un entorno virtual.
- **Ejecución:** solo copia ese entorno virtual (sin pip ni el código fuente) y corre con un usuario sin privilegios.

```bash
docker build -t bitcoin-backend .
```

```bash
docker run --rm -p 8080:8080 bitcoin-backend
```

```bash
curl localhost:8080/health
```

Otro puerto y datos persistentes en una carpeta del equipo:

```bash
docker run --rm -e PORT=9090 -p 9090:9090 -e DATA_DIR=/app/data -v "$(pwd)/data:/app/data" bitcoin-backend
```

## Despliegue en Railway

Railway detecta el `Dockerfile` y construye la imagen.

1. Crea un proyecto desde este repositorio (hay que autorizar a Railway en la organización de GitHub).
2. **Variables:**
   - `ORIGEN_PERMITIDO` = URL exacta del frontend (nunca `*`: la cookie de sesión necesita credenciales).
   - `CLAVE_CIFRADO` = una clave nueva, marcada como secreta (ver [docs/SEGURIDAD.md](docs/SEGURIDAD.md)).
   - `COOKIE_SEGURA=true` y `CONFIAR_PROXY=true`.
   - **No definas `PORT`:** Railway lo pone solo.
3. **Networking:** genera un dominio público.
4. **Settings:** escribe `/health` como ruta del healthcheck. Ese endpoint nunca consulta Binance, así que responde aunque Binance falle.
5. **Persistencia:** el disco del contenedor **se borra en cada despliegue**. Para que la cartera y las órdenes sobrevivan:
   - Agrega un volumen montado en `/data`.
   - Define `DATA_DIR=/data`.
   - Define también `RAILWAY_RUN_UID=0`. Railway monta los volúmenes como root y la imagen corre con un usuario sin privilegios; sin esa variable no podría escribir en el volumen ([documentación de volúmenes de Railway](https://docs.railway.com/volumes)).

   Sin volumen, cada despliegue empieza con 10 000 USDT nuevos.
6. **Error de región:**
   - **Síntoma:** si `/api/velas` responde 502 y el registro dice *"Binance no está disponible desde esta región; cambia la región del servicio o la URL base"*, Binance bloquea la región del servidor (por ejemplo, EE. UU.).
   - **Solución:** cambia la región del servicio en Railway, o prueba otra `BINANCE_BASE_URL`.

**Listo cuando:** `https://tu-dominio/health` responde `{"estado":"ok"}` y `/api/velas?intervalo=1d&cantidad=5` devuelve velas reales.

## Endpoints

Detalle, parámetros y ejemplos en [docs/API.md](docs/API.md).

| Método y ruta | Qué hace |
| --- | --- |
| `GET /health` | Estado del servicio, sin consultar Binance |
| `GET /api/precio` | Último precio de BTCUSDT |
| `GET /api/velas?intervalo=1d&cantidad=200` | Velas (1m, 5m, 15m, 1h, 4h, 1d; hasta 1000) |
| `GET /api/indicadores?indicador=rsi&periodo=14` | Indicador técnico: sma, ema, rsi, macd, bollinger, volatilidad |
| `GET /api/senal?estrategia=combinada` | Decisión más reciente y pronóstico de una estrategia |
| `GET /api/backtest?estrategia=cruce&capital=1000` | Backtest y validación entrenamiento/prueba (70/30) |
| `POST /api/ordenes` | Crea una orden simulada `{"tipo":"COMPRA","monto":500}`. Órdenes, cartera, historial y bot son de cada usuario y exigen sesión |
| `GET /api/ordenes?estado=PENDIENTE` | Lista órdenes |
| `GET /api/ordenes/{id}` | Una orden |
| `DELETE /api/ordenes/{id}` | Cancela una orden pendiente |
| `POST /api/ordenes/procesar` | Ejecuta la siguiente orden de la cola |
| `POST /api/ordenes/deshacer` | Deshace la última orden creada si sigue pendiente |
| `GET /api/cartera` | Cartera simulada valorada al precio actual |
| `GET /api/historial?limite=50` | Historial de eventos, el más reciente primero |
| `POST /api/bot/iniciar` | Pone en marcha el bot simulado (configuración opcional en el cuerpo) |
| `POST /api/bot/detener` | Detiene el bot |
| `GET /api/bot/estado` | Estado del bot y su última decisión |
| `GET /api/stream` | Eventos en tiempo real (SSE): `precio`, `orden`, `cartera`, `senal` |
| `POST /api/cuentas/registro` | Crea una cuenta (cédula, nombre, apellido, correo, teléfono y contraseña) |
| `POST /api/sesion` · `POST /api/sesion/codigo` · `DELETE /api/sesion` | Iniciar sesión (con código de 6 dígitos si hay verificación en dos pasos) y cerrarla |
| `GET /api/cuentas/yo` | La cuenta de la sesión actual |
| `/api/cuentas/dos-pasos…`, `/api/cuentas/sesiones…`, `/api/cuentas/actividad`, `/api/cuentas/contrasena` | Centro de seguridad |

## Estructuras de datos

Están en `src/bitcoinai/estructuras`:
- Son genéricas e implementadas a mano con nodos enlazados. La lógica del proyecto no usa `list`, `collections.deque`, `queue.Queue` ni `heapq` como estructuras; las listas de Python solo aparecen en la frontera JSON (lo que entra y sale por HTTP o a disco). Una prueba revisa el código de las estructuras con el árbol sintáctico para asegurarlo.
- Cada operación documenta su complejidad. La tabla completa está en [docs/ESTRUCTURAS.md](docs/ESTRUCTURAS.md).

| Estructura | Dónde se usa | Por qué esa estructura |
| --- | --- | --- |
| **ListaDoble** | Velas de mercado (`ClienteBinance`, indicadores, `Backtester`) | Las velas nuevas entran por el final y las viejas salen por el inicio en O(1) (`conservar_ultimos` para las ventanas de SMA, Bollinger y volatilidad). Se recorre hacia atrás para unir los lotes de Binance y para tomar los valores más recientes (`ultimos`). |
| **ListaDoble** | Clientes de `/api/stream` (`Publicador`) | Cada cliente guarda su nodo; al desconectarse se quita con `eliminar_nodo` en O(1), sin recorrer la lista. |
| **Cola** | Órdenes pendientes (`LibroDeOrdenes`) y buzón de cada cliente de `/api/stream` | Se atienden en orden de llegada (FIFO). Cancelar una orden del medio reconstruye la cola en O(n) conservando el orden de las demás. |
| **Pila** | Historial de eventos y de decisiones (`LibroDeOrdenes`, `Backtester`) | El evento más reciente queda arriba (LIFO). Otra pila de ids permite deshacer la última orden, y luego la anterior. |
| **Lista** | Registro de órdenes terminadas y operaciones cerradas del backtest | Se agregan al final en O(1) y se recorren para mostrar y calcular métricas. |
| **Cola** | Límite de intentos de inicio de sesión (`LimitadorIntentos`) | Ventana deslizante: los intentos vencidos salen por el frente, O(1) amortizado por intento. |

Las estrategias recuerdan el estado de sus indicadores entre velas (memoria incremental), así que un backtest cuesta O(n) y no O(n²).

## Estructura del código

Paquetes bajo `src/bitcoinai`:

| Paquete | Contenido |
| --- | --- |
| `estructuras` | Lista, ListaDoble, Cola y Pila |
| `modelo` | Vela e Intervalo |
| `mercado` | Cliente de Binance, caché y validación de velas |
| `indicadores` | Indicadores técnicos y sus versiones incrementales |
| `estrategia` | Estrategias, pronóstico, backtest y validación |
| `simulacion` | Cartera, libro de órdenes y bot |
| `persistencia` | Guardado en archivos JSON |
| `basedatos` | Conexión SQLite y migraciones |
| `seguridad` | Argon2id, cifrado, verificación en dos pasos y límites de intentos |
| `usuarios` | Cuentas: validación, registro, sesiones y actividad |
| `api` | Aplicación FastAPI, middlewares, endpoints y SSE |

Las pruebas están en `tests/`, con la misma organización.

En cada push y pull request, GitHub Actions corre `ruff check`, `mypy src` y `pytest` con Python 3.13, y después construye la imagen Docker y comprueba que `/health` responda (`.github/workflows/ci.yml`).
