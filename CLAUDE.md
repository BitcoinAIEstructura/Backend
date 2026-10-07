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

## Convenciones
- Cada clase pública lleva pruebas JUnit.
- Comentarios en español que expliquen la complejidad (Big O) de cada operación de las estructuras.
- No hacer commit ni push salvo que el usuario lo pida.

## Fases
- [ ] 1. Estructuras de datos
- [ ] 2. Datos de mercado (Binance)
- [ ] 3. API HTTP
- [ ] 4. Indicadores técnicos
- [ ] 5. Señales y backtesting
- [ ] 6. Simulación de operaciones
- [ ] 7. Tiempo real y persistencia
- [ ] 8. Docker y Railway
