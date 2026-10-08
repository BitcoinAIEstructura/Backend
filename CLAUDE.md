# Backend: bot de IA para el mercado de Bitcoin

## Objetivo
Backend que obtiene velas de BTCUSDT de Binance, calcula indicadores, genera señales, simula operaciones y expone todo por HTTP. **No opera con dinero real.**

## Reglas
- Java 21.
- Sin Spring ni otros frameworks.
- Servidor HTTP con `com.sun.net.httpserver`.
- Cliente HTTP con `java.net.http.HttpClient`.
- JSON escrito a mano (lector y escritor propios).
- La única dependencia externa permitida es JUnit 5, en alcance `test`.
- **Todo es simulado:** el backend nunca se conecta a una cuenta real de un exchange ni usa claves de API de exchanges. Solo lee datos públicos de mercado.

## Estructuras de datos
- `Lista`, `ListaDoble`, `Cola` y `Pila` se implementan a mano con nodos enlazados.
- Prohibido usar `ArrayList`, `LinkedList`, `ArrayDeque`, `Stack` o `Queue` del JDK para la lógica del proyecto.
- Nombres de clases y métodos de las estructuras en español.

## Paquetes (bajo `com.bitcoinai.backend`)
`estructuras`, `modelo`, `mercado`, `indicadores`, `estrategia`, `simulacion`, `api`, `persistencia`, `util`.

## Comandos
- Pruebas: `mvn test`
- Empaquetar: `mvn package` (genera `target/backend-1.0.0-SNAPSHOT.jar`)
- Ejecutar: `java -jar target/backend-1.0.0-SNAPSHOT.jar`
- Prueba manual con Binance real (necesita internet): `mvn test -Dtest=ClienteBinanceManualTest -Djunit.jupiter.conditions.deactivate=org.junit.*DisabledCondition`

## Convenciones
- Cada clase pública lleva pruebas JUnit.
- Comentarios en español que expliquen la complejidad (Big O) de cada operación de las estructuras.
- No hacer commit ni push salvo que el usuario lo pida.

## Fases
- [x] 1. Estructuras de datos (ver `docs/ESTRUCTURAS.md`)
- [x] 2. Datos de mercado (Binance)
- [x] 3. API HTTP (ver `docs/API.md`)
- [x] 4. Indicadores técnicos
- [x] 5. Señales y backtesting
- [x] 6. Simulación de operaciones
- [x] 7. Tiempo real y persistencia
- [x] 8. Docker y Railway (ver `README.md`; los pasos en el panel de Railway los hace el usuario)
