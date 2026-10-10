# Backend: bot de IA para el mercado de Bitcoin (Python)

## Objetivo
Backend que obtiene velas de BTCUSDT de Binance, calcula indicadores, genera señales, simula operaciones y expone todo por HTTP. **No opera con dinero real.**

## Reglas
- Python 3.13.
- API con FastAPI + uvicorn. pydantic solo dentro del paquete `api`; el dominio no depende de FastAPI.
- Cliente HTTP de Binance con httpx.
- Base de datos SQLite con el módulo estándar `sqlite3`; consultas siempre con parámetros (`?`) y cambios de esquema solo con migraciones nuevas en `basedatos/migraciones.py`.
- Seguridad: contraseñas con Argon2id (argon2-cffi), datos personales cifrados con AES-GCM (cryptography). Nunca registrar contraseñas, tokens ni datos personales en los logs. Ver `docs/SEGURIDAD.md`.
- JSON con el módulo `json` estándar.
- Tipado completo: `mypy --strict` debe pasar.
- **Todo es simulado:** nunca se conecta a una cuenta real de un exchange ni usa claves de API de exchanges. Solo lee datos públicos de mercado.

## Estructuras de datos
- `Lista`, `ListaDoble`, `Cola` y `Pila` se implementan a mano con nodos enlazados.
- Prohibido usar `list`, `collections.deque`, `queue.Queue` o `heapq` como estructura en la lógica del proyecto. Única excepción, los bordes con JSON: el módulo `json` entrega los arreglos como `list` (respuestas de Binance, archivos guardados) y FastAPI necesita `list` para escribir la respuesta. Ahí se lee o se arma la `list` y enseguida se pasa a (o desde) nuestras estructuras.
- `dict` sí se permite para mapas (como `Map` en Java): objetos JSON, cachés y parámetros.
- Nombres de clases y métodos en español; funciones y métodos en snake_case (`agregar_final`, `esta_vacia`).

## Migración desde Java
- La versión Java completa está en la etiqueta `java-final`. Se consulta con `git show java-final:<ruta>`, por ejemplo `git show java-final:src/main/java/com/bitcoinai/backend/estructuras/Lista.java`.
- Se porta el comportamiento y las pruebas con los mismos valores esperados, escribiendo Python idiomático; no se traduce línea por línea.
- El contrato `docs/API.md` no cambia: mismas rutas, parámetros, códigos y forma del JSON. El frontend no debe notar la migración.
- La guía de prompts está en `docs/GUIA-MIGRACION-PYTHON.md`.

## Paquetes (bajo `src/bitcoinai`)
`estructuras`, `modelo`, `mercado`, `indicadores`, `estrategia`, `simulacion`, `api`, `persistencia`, `basedatos`, `seguridad`, `usuarios`. Pruebas en `tests/`.

## Comandos
- Crear el entorno (una vez): `py -3.13 -m venv .venv`
- Activarlo: `.venv\Scripts\activate` (Windows) o `source .venv/bin/activate` (Linux/macOS)
- Instalar: `pip install -e ".[dev]"`
- Pruebas: `pytest`
- Prueba manual con Binance real (necesita internet): `pytest -m manual -s`
- Estilo: `ruff check` (corregir orden de imports: `ruff check --fix`)
- Tipos: `mypy src`
- Ejecutar: `python -m bitcoinai`

## Convenciones
- Cada módulo público lleva pruebas pytest.
- Docstrings en español; en las estructuras, cada operación indica su complejidad ("Complejidad: O(1)").
- No hacer commit ni push salvo que el usuario lo pida.

## Fases
- [x] 1. Estructuras de datos (ver `docs/ESTRUCTURAS.md`)
- [x] 2. Datos de mercado (Binance)
- [x] 3. API HTTP (contrato en `docs/API.md`; documentación interactiva en `/docs`)
- [x] 4. Indicadores técnicos
- [x] 5. Señales y backtesting (con memoria incremental: el backtest es O(n))
- [x] 6. Simulación de operaciones
- [x] 7. Tiempo real y persistencia
- [x] 8. Docker y Railway

## Etapa 2: plataforma (el frontend nuevo está en otro repositorio)
- [x] 1. Usuarios y seguridad: registro con CC/CE, Argon2id, datos cifrados, sesiones con cookie, 2FA (TOTP), límites de intentos, actividad
- [x] 2. Cada usuario con su propia simulación (cartera, órdenes y bot), guardada en la base de datos
- [ ] 3. Frontend nuevo: inicio de sesión con moneda 3D y diseño futurista adaptable
- [ ] 4. Panel con gráficas en vivo
- [ ] 5. Estructuras avanzadas (montículo, árbol AVL, tabla hash, cola circular, trie) y pantalla "Cómo funciona"
- [ ] 6. IA: regresión logística, árbol de decisión, k vecinos y comité
- [ ] 7. Seguridad extra y pulido
- [ ] 8. Entrega: despliegue, documentación y presentación
