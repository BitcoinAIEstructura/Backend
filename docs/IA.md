# Inteligencia artificial

Tres modelos clásicos de aprendizaje supervisado, programados a mano en `bitcoinai.ia` sin librerías de aprendizaje automático, más un comité que los combina. Todos responden lo mismo: **¿la próxima vela cerrará más arriba que la actual?**

> El mercado es en gran parte impredecible. Una exactitud del 52 % al 55 % ya es mucho para este problema, y la del pasado no garantiza la del futuro. Por eso cada modelo se compara siempre con una **base**: decir siempre lo que más pasó.

## Datos

- **Muestras:** `caracteristicas.py` convierte cada vela en una muestra. La etiqueta es 1 si la siguiente cerró más arriba.
- **Calentamiento:** las primeras 50 velas se usan solo para calcular la SMA 50.
- **Sin mirar el futuro:** las características usan la vela actual y las anteriores. Hay una prueba que lo comprueba.
- **Acceso en O(1):** las velas se copian a un `Arreglo` para leer "hace 20 velas" sin recorrer nodos.

| Característica | Qué mide |
| --- | --- |
| Rendimiento de 1, 5 y 20 velas | Cuánto subió o bajó el precio en ese plazo |
| RSI 14 | Fuerza relativa, de 0 a 100 |
| Histograma del MACD | Impulso, dividido entre el precio para comparar épocas |
| Volatilidad de 20 velas | Desviación de los rendimientos |
| Distancia a la SMA 20 | Qué tan lejos está el precio de su media |
| SMA 20 frente a SMA 50 | Tendencia corta contra tendencia larga |
| Volumen relativo | Volumen de la vela frente a su promedio de 20 |
| Rango de la vela | (máximo − mínimo) ÷ cierre |

### Fuentes externas (`bitcoinai.externos`)

Además del precio, los modelos aprenden de tres fuentes públicas (sin cuentas ni claves; solo se leen datos):

| Fuente | Características | Qué es |
| --- | --- | --- |
| Índice de miedo y codicia (alternative.me) | Valor de 0 a 100 y su cambio en 7 días | El ánimo del mercado, un valor por día desde 2018 |
| Futuros de Binance (fapi.binance.com) | Última tasa de financiación y su promedio de 24 h (en ‰) | Quién le paga a quién cada 8 horas: si es positiva, hay más apuestas a que sube |
| Opciones de Deribit | DVOL y su cambio en 24 h | La volatilidad anual que esperan las opciones para los próximos 30 días |

- **Sin mirar el futuro:** cada dato se guarda con el momento en que **ya se conocía** (el DVOL de una hora, al terminar esa hora; la financiación, al pagarse) en una `SerieTemporal`, que es un `ArbolAVL`. Para cada vela se toma el `piso` en su cierre: el último valor conocido entonces, en O(log n).
- **Sin inventar datos:** una fuente entra solo si tiene valor para todas las velas. Si su historial es más corto o no responde, se entrena sin ella y la página lo dice.
- **¿Ayudan de verdad?** La misma regresión logística se entrena dos veces, solo con el precio y con todo, y se mide en las mismas velas de prueba. La página muestra las dos exactitudes y una conclusión en palabras; puede salir que no ayudan, y se dice.
- **Lo de ahora** (`GET /api/ia/fuentes`): el valor de hoy de cada fuente, la proporción de cuentas de futuros que apuestan a que sube y el **movimiento esperado** por vela, que sale del DVOL: DVOL ÷ 100 × √(segundos de la vela ÷ segundos del año). Con DVOL 40 y velas de 1 hora, unos ±0,43 %.
- **Polymarket y Kalshi** (mercados de predicciones) se evaluaron, pero están bloqueados en Colombia, así que no se usan.
- **Caché:** una hora para las series y 10 minutos para lo de ahora; las fuentes se piden a la vez, en hilos.

**Escalado.** El RSI va de 0 a 100 y un rendimiento ronda 0,01. Sin escalar, el RSI dominaría las distancias y los pasos del gradiente. Por eso cada característica se pasa a desviaciones respecto del promedio, y la media y la desviación se aprenden solo con el entrenamiento.

## Modelos

### Regresión logística (`logistica.py`)

- **Fórmula:** `P(sube) = sigmoide(b + w·x)`.
- **Entrenamiento:** descenso por gradiente sobre el error logarítmico, con regularización L2 para que no memorice el ruido. Cuesta O(épocas · n · d).
- **Explicación:** el aporte `wⱼ·xⱼ` de cada característica, ordenado por peso con un montículo.

### Árbol de decisión (`arbol.py`)

- **Tipo:** CART con impureza de Gini.
- **Cortes:** en cada nodo prueba 15 cortes por característica y elige el que más baja el Gini.
- **Límites:** para en la profundidad 4 o si una hoja quedaría con menos de 20 muestras.
- **Probabilidad de la hoja:** `(subidas + 1) / (n + 2)`, con suavizado de Laplace.
- **Explicación:** el camino exacto de preguntas y cuántas veces subió en esa hoja.

### k vecinos (`vecinos.py`)

- **Cómo funciona:** guarda el pasado y busca las 15 velas más parecidas, con distancia euclidiana entre características escaladas.
- **Elegir los 15:** usa un montículo de máximos de tamaño k, con abandono temprano de la suma. Cuesta O(n · d + n log k).
- **Probabilidad:** cuántos de esos k subieron después.

### Comité (`comite.py`)

- **Cómo combina:** promedio ponderado de las probabilidades de los tres.
- **Pesos:** cuánto supera cada uno a la base en una **validación dentro del entrenamiento**, nunca en la prueba final. Todos tienen un peso mínimo de 5 %.

## Evaluación honesta (`evaluacion.py`)

- **División en el tiempo:** se entrena con el 80 % más viejo y se prueba con el 20 % más reciente. Mezclar al azar sería trampa: el modelo vería días posteriores a los que después "predice".
- **Métricas:** exactitud, base, ventaja sobre la base y precisión al decir "sube".

## Servicio y API

`ServicioIA` pide las últimas 1000 velas cerradas y las series externas, entrena, mide y predice. Los textos que muestra la página (qué hace cada modelo, el veredicto frente a la base, la conclusión sobre las fuentes externas y los nombres de los intervalos) salen de `textos.py`: el frontend solo los dibuja. Guarda el resultado de cada intervalo 10 minutos, porque entrenar con 1000 velas tarda unos 3 s. El endpoint es `GET /api/ia/predicciones` (ver [API.md](API.md)).
