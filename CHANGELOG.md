# Changelog

Todos los cambios relevantes de este proyecto se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado usa [SemVer](https://semver.org/lang/es/).

## [2.0.0] - 2026-11-07

Versión inicial del backend en Python/FastAPI.

### Agregado

- Datos de mercado de Binance con caché por TTL: precio, velas y precios recientes.
- Indicadores técnicos: SMA, EMA, RSI, MACD, Bollinger y volatilidad.
- Estrategias de señal y backtest con validación entrenamiento/prueba (70/30).
- Simulación por usuario: órdenes, cartera, historial y bot automático.
- Eventos en tiempo real por SSE en `/api/stream` (`precio`, `orden`, `cartera`, `senal`).
- Cuentas con Argon2, sesiones por cookie, verificación de correo y verificación en dos pasos (TOTP).
- Centro de seguridad: sesiones activas, actividad reciente y cambio de contraseña.
- Alertas de precio por usuario.
- Asistente conversacional con los datos de la sesión.
- Liga de inversores con alias públicos y ranking.
- Predicciones de IA y resumen de fuentes externas.
- Búsqueda global de páginas, acciones, indicadores y conceptos.
- Persistencia en SQLite con migraciones y simulación en JSON.
- Estructuras de datos propias: listas, cola, pila, montículo, tabla hash, trie y árbol AVL.
- Límite de intentos, límite de peticiones por IP y encabezados de seguridad.
- Docker, configuración para Railway y revisión continua con Ruff, mypy y pytest.
