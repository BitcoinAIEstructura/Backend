# Estructuras de datos

Todas están en el paquete `bitcoinai.estructuras`:
- **Genéricas:** se declaran como `Lista[T]`, `ListaDoble[T]`, etc.
- **Hechas a mano:** con nodos enlazados (`NodoSimple`, `NodoDoble`, `NodoAVL`, `NodoTrie`) o sobre un `Arreglo` de tamaño fijo, sin `list`, `collections.deque`, `queue.Queue` ni `heapq` por dentro. Una prueba de guardia (`tests/estructuras/test_sin_colecciones.py`) revisa el código y falla si aparece alguna colección de Python.
- **Contador propio:** siempre se lleva la cuenta de elementos, así que `tamanio()`, `esta_vacia()` y `len()` cuestan O(1).
- **Errores:** si se lee o se quita algo de una estructura vacía se lanza `EstructuraVaciaError`; si se usa un índice inválido, `IndiceFueraDeRangoError`. Nunca se devuelve `None` en esos casos.
- **Índices:** van de 0 a `tamanio() - 1`. No se aceptan índices negativos como en las listas de Python.
- **Recorrido:** `Lista` y `ListaDoble` se recorren con `for` (implementan `__iter__`). `Cola` y `Pila` no se recorren: solo dejan ver el frente o el tope.

## Uso en el proyecto

| Estructura | Uso |
| --- | --- |
| `ListaDoble` | Ventana de velas: las nuevas entran por el final, las más antiguas salen por el inicio con `conservar_ultimos(n)`, y los indicadores la recorren en los dos sentidos. |
| `Cola` | Órdenes pendientes: se ejecutan en el mismo orden en que llegaron (FIFO). |
| `Pila` | Historial de decisiones y eventos: el más reciente queda arriba (LIFO). |
| `Lista` | Operaciones cerradas: se agregan al final y se recorren para calcular métricas. |
| `Arreglo` | Base del montículo, la cola circular y la tabla hash: casillas con acceso por índice en O(1). |
| `Monticulo` | Liga de inversores: los 10 mejores de n usuarios en O(n log 10). |
| `ArbolAVL` | "¿Y si hubiera invertido?": las velas diarias indexadas por fecha. |
| `TablaHash` | La simulación de cada usuario por su id, y resultados sin repetir en la búsqueda. |
| `ColaCircular` | Los últimos 120 precios, con memoria fija. |
| `Trie` | La búsqueda de Ctrl + K mientras se escribe. |

### Dónde está cada uso en el código

Las clases conservan el nombre que tenían en Java.

| Estructura | Clase | Para qué |
| --- | --- | --- |
| `ListaDoble[Vela]` | `ClienteBinance` | Junta los lotes de velas: recorre cada lote con `iterador_atras()` y agrega al inicio, descartando duplicados |
| `ListaDoble[float]` | `Sma`, `BandasBollinger`, `Volatilidad` | Ventana deslizante con `conservar_ultimos(p)`: O(n) en total |
| `ListaDoble[T]` | `Series.ultimos` | Toma los n valores más recientes empezando por la cola: O(n) y no O(tamaño total) |
| `ListaDoble[Vela]` | `Backtester` | Velas "hasta ahora": se agrega una al final por vuelta, así la estrategia nunca ve el futuro |
| `ListaDoble[float]` | `SmaIncremental` | Ventana de la memoria incremental de las estrategias: cada vela nueva cuesta O(1) |
| `ListaDoble[Vela]` | `Estrategia` (memoria incremental) | Detecta en O(1) si recibe la misma lista con una vela más, comparando la primera y la penúltima (`obtener(n − 2)` llega desde la cola) |
| `ListaDoble[Vela]` | `velas_cerradas` | Quita la vela en curso con `eliminar_ultimo()`, O(1) |
| `Pila[Decision]` | `Backtester` | Historial de decisiones; al desapilar salen de la más nueva a la más vieja |
| `Lista[OperacionCerrada]` | `Backtester` | Operaciones del backtest, en orden |
| `Cola[Orden]` | `LibroDeOrdenes` | Órdenes pendientes, FIFO |
| `Lista[Orden]` | `LibroDeOrdenes` | Registro de órdenes ejecutadas, canceladas y rechazadas |
| `Pila[Evento]` | `LibroDeOrdenes` | Historial de eventos, el más reciente arriba |
| `Pila[int]` | `LibroDeOrdenes` | Ids en orden de creación, para deshacer la última orden (y la anterior, y la anterior…) |
| `ListaDoble[Suscriptor]` | `Publicador` | Clientes conectados a `/api/stream`; cada uno guarda su nodo para quitarlo en O(1) al desconectarse |
| `Cola[str]` | `Suscriptor` | Buzón de cada cliente de `/api/stream`: el publicador encola desde cualquier hilo y la respuesta HTTP desencola en orden, O(1) cada uno |
| `Cola[float]` | `LimitadorIntentos` | Momentos de los intentos de inicio de sesión por correo o IP: los vencidos salen por el frente (ventana deslizante, O(1) amortizado) |
| `ListaDoble[Suscriptor]` | `Publicador.publicar_a` | Los eventos privados se entregan solo a los suscriptores de ese usuario, recorriendo la lista una vez (O(n)) |
| `TablaHash[int, SimulacionUsuario]` | `GestorSimulaciones` | La simulación de cada usuario por su id, en O(1) en promedio (antes era un `dict`) |
| `Lista[Orden]`, `Lista[int]`, `Lista[Evento]` | `EstadoSimulacion` | Foto del libro de órdenes para guardarla en disco, en el orden en que hay que recargarla |
| `Monticulo[Participante]` | `ranking.mejores` | Montículo de mínimos de tamaño k: su tope es el peor de los k mejores; cada usuario entra solo si lo supera (`reemplazar_tope`) |
| `ArbolAVL[int, Vela]` | `IndiceVelas` | `techo(fecha)` da la vela de un día en O(log n); `rango(fecha, hoy)` recorre solo las de después |
| `TablaHash[int, None]`, `TablaHash[str, None]` | `Buscador` | Junta las entradas de cada palabra sin repetirlas y cruza las de varias palabras |
| `Trie[Lista[int]]` | `Buscador` | Cada palabra normalizada lleva a las entradas del catálogo donde aparece |
| `ColaCircular[tuple[int, float]]` | `PreciosRecientes` | Últimos 120 precios: el nuevo pisa al más viejo en O(1) |
| `Pila[int]` (auxiliar) | `LibroDeOrdenes.pila_deshacer` | Lee los k próximos ids a deshacer sin perderlos |

### Quitar un elemento por su nodo en O(1) (tiempo real)

El `Publicador` guarda los clientes de `/api/stream` en una `ListaDoble[Suscriptor]`. Al conectarse un cliente se lo agrega con `agregar_final_nodo(suscriptor)`, que devuelve el nodo, y el suscriptor lo guarda. Cuando el cliente se desconecta, se llama a `eliminar_nodo(nodo)`:

- **Por qué es O(1):** el nodo ya conoce a su anterior y a su siguiente, así que basta con unirlos entre sí (y mover la cabeza o la cola si era un extremo). No hay que recorrer la lista para buscarlo.
- **Comparación:** en una lista simple habría que recorrerla para encontrar el nodo anterior, O(n). Buscar por valor también sería O(n).
- **Seguridad:** cada nodo recuerda a qué lista pertenece y en qué "generación" se creó. Quitarlo dos veces, o pasar un nodo de otra lista o de antes de un `vaciar()`, devuelve `False` en vez de romper la estructura.

### Memoria incremental (backtest en O(n) y no en O(n²))

En cada vela el backtest le entrega a la estrategia la lista de velas "hasta ahora".

- **El problema:** recalcular los indicadores desde la primera vela en cada paso cuesta O(n) por vela, O(n²) en total. En Python, un backtest de 1000 velas con la estrategia combinada tardaba 7,6 s.
- **La solución:** cada estrategia recuerda el estado de sus indicadores: la ventana y la suma de la SMA (con una `ListaDoble`), los promedios del RSI y las EMA del MACD. Si recibe la misma lista con una vela más al final, procesa solo esa vela, en O(1). Si recibe otra lista, recalcula desde cero.
- **Resultado:** el backtest bajó a 0,02 s.
- **Por qué es honesto:** lo que recuerda sale solo de velas ya recibidas, así que no mira el futuro.
- **Mismos resultados:** una prueba (`tests/estrategia/test_incremental.py`) comprueba que da exactamente las mismas decisiones que recalcular cada prefijo desde cero.

### Guardar y recargar sin perder el orden (persistencia)

- **Cola:** se guarda leyéndola en orden con la rotación (desencolar y volver a encolar) y se reconstruye encolando en ese mismo orden. El frente sigue siendo el frente.
- **Pila:** se guarda del fondo al tope. Para eso se desapila todo a una auxiliar, que queda con el fondo arriba, y al devolver los elementos salen del fondo al tope. Se reconstruye apilando en ese orden, así el más reciente queda otra vez arriba. Es O(n).

### Técnicas con cola y pila (simulación)

Una cola solo deja ver el frente y una pila solo el tope. Para lo demás, el `LibroDeOrdenes` usa:

- **Leer la cola sin perderla:** se desencola cada orden y se vuelve a encolar. Tras n vueltas la cola queda igual. O(n).
- **Cancelar una orden del medio:** igual que lo anterior, pero la cancelada no se vuelve a encolar. Las demás conservan su orden. O(n).
- **Devolver una orden al frente** (si falla la consulta del precio): se pasa todo a una cola auxiliar, se encola la orden y luego se devuelve el resto. O(n).
- **Leer los k eventos más recientes sin perderlos:** se desapilan k a una pila auxiliar y luego se devuelven. Quedan en el mismo orden. O(k).

## Lista (simplemente enlazada, con cabeza y cola)

| Operación | Complejidad | Nota |
| --- | --- | --- |
| `agregar(valor)` | O(1) | Usa la referencia a la cola |
| `agregar_inicio(valor)` | O(1) | |
| `insertar_ordenado(valor, clave)` | O(n) | Recorre hasta la posición; estable con iguales. `clave` funciona como en `sorted` |
| `obtener(indice)` | O(n) | O(1) para el primero y el último |
| `eliminar(indice)` | O(n) | Hay que llegar al nodo anterior; O(1) para el primero |
| `buscar(condicion)` | O(n) | Devuelve el índice o -1 |
| `primero()`, `ultimo()` | O(1) | |
| `tamanio()`, `esta_vacia()`, `vaciar()`, `len()` | O(1) | |
| Recorrido con `for` | O(n) | |

## ListaDoble (doblemente enlazada, con cabeza y cola)

| Operación | Complejidad | Nota |
| --- | --- | --- |
| `agregar_inicio(valor)`, `agregar_final(valor)` | O(1) | |
| `agregar_final_nodo(valor)` | O(1) | Igual que `agregar_final`, pero devuelve el nodo |
| `eliminar_nodo(nodo)` | O(1) | Quita ese nodo sin recorrer la lista; `False` si no pertenece |
| `insertar(indice, valor)` | O(min(i, n − i)) | Llega desde el extremo más cercano |
| `obtener(indice)` | O(min(i, n − i)) | Peor caso O(n/2) |
| `eliminar_primero()`, `eliminar_ultimo()` | O(1) | Cada nodo conoce a su anterior |
| `eliminar(indice)` | O(min(i, n − i)) | Llegar al nodo; desenlazarlo es O(1) |
| `primero()`, `ultimo()` | O(1) | |
| `conservar_ultimos(n)` | O(k) | k = elementos descartados |
| `tamanio()`, `esta_vacia()`, `vaciar()`, `len()` | O(1) | |
| `iterador_adelante()`, `iterador_atras()`, `for` | O(n) | Crear el iterador es O(1); cada paso es O(1) |

## Cola (FIFO, con frente y final)

| Operación | Complejidad |
| --- | --- |
| `encolar(valor)` | O(1) |
| `desencolar()` | O(1) |
| `ver_frente()` | O(1) |
| `tamanio()`, `esta_vacia()`, `vaciar()`, `len()` | O(1) |

## Pila (LIFO, con tope)

| Operación | Complejidad |
| --- | --- |
| `apilar(valor)` | O(1) |
| `desapilar()` | O(1) |
| `ver_tope()` | O(1) |
| `tamanio()`, `esta_vacia()`, `vaciar()`, `len()` | O(1) |

## Arreglo (tamaño fijo)

Es como `new T[n]` en Java: casillas contiguas, hechas con `ctypes.py_object * n`. No es una `list`: no crece ni tiene `append`. Para agrandarlo se crea uno más grande y se copia.

| Operación | Complejidad |
| --- | --- |
| `Arreglo(capacidad)` | O(n): deja cada casilla en `None` |
| `obtener(i)`, `poner(i, valor)`, `intercambiar(i, j)` | O(1) |
| `copiar_en(destino, cantidad)` | O(cantidad) |
| `capacidad()`, `len()` | O(1) |

## Monticulo (cola de prioridad, binario)

Es un árbol binario completo guardado nivel por nivel en un `Arreglo`. Los hijos de la casilla `i` están en `2i + 1` y `2i + 2`, y su padre en `(i − 1) // 2`. Cada padre tiene prioridad sobre sus hijos, así que el tope está siempre en la casilla 0.

- **Prioridad:** la da `clave`, como en `sorted`. Por defecto sale primero la menor; con `mayor_primero=True`, la mayor.
- **Empates:** con claves iguales sale primero el que llegó antes, así que es estable.

| Operación | Complejidad | Cómo |
| --- | --- | --- |
| `insertar(valor)` | O(log n), O(1) amortizado al crecer | Entra al final y sube intercambiándose con el padre |
| `extraer()` | O(log n) | El último pasa a la raíz y baja por el hijo de más prioridad |
| `reemplazar_tope(valor)` | O(log n) | Saca el tope y mete otro en un solo paso (los k mejores) |
| `ver_tope()` | O(1) | |
| `en_orden_de_arreglo()` | O(n) | Para dibujarlo |
| `intercambios_ultima_operacion()` | O(1) | Cuántos niveles subió o bajó |

## ArbolAVL (árbol binario de búsqueda balanceado)

Es un mapa ordenado `clave → valor`: las claves menores van a la izquierda y las mayores a la derecha.

- **Balance:** después de cada cambio revisa los nodos del camino. Si un lado quedó dos niveles más alto, rota:
  - **Rotación simple** en los casos izquierda-izquierda y derecha-derecha.
  - **Rotación doble** en los casos izquierda-derecha y derecha-izquierda.
- **Altura:** nunca pasa de ~1,44·log₂(n), aunque las claves lleguen ordenadas. Las velas llegan así: 1000 velas quedan en 10 niveles, no en 1000.

| Operación | Complejidad |
| --- | --- |
| `insertar(clave, valor)`, `eliminar(clave)` | O(log n) |
| `buscar(clave)`, `contiene(clave)` | O(log n) |
| `techo(clave)` (primera mayor o igual), `piso(clave)` (última menor o igual) | O(log n) |
| `minimo()`, `maximo()` | O(log n) |
| `rango(desde, hasta)` | O(log n + k), con k resultados |
| `en_orden()` | O(n) |
| `altura()`, `tamanio()`, `rotaciones_ultima_operacion()` | O(1) |

## TablaHash (encadenamiento separado)

- **Cubetas:** un `Arreglo` cuya capacidad es siempre potencia de 2. La cubeta de una clave es `hash & (capacidad − 1)`, después de mezclar los bits altos con los bajos para que ids seguidos no se amontonen.
- **Colisiones:** las claves que caen en la misma cubeta se encadenan en una lista enlazada.
- **Crecimiento:** si el factor de carga (elementos ÷ cubetas) pasaría de 0,75, la tabla duplica las cubetas y reubica cada entrada (rehash).

| Operación | Complejidad |
| --- | --- |
| `poner(clave, valor)` | O(1) en promedio; O(n) cuando crece, O(1) amortizado |
| `obtener(clave)`, `contiene(clave)`, `eliminar(clave)` | O(1) en promedio |
| `elementos()`, `valores()`, `claves_por_cubeta()`, `longitudes_de_cubetas()` | O(n + capacidad) |
| `capacidad()`, `factor_de_carga()`, `tamanio()` | O(1) |

## ColaCircular (búfer de anillo)

- **Cómo guarda:** guarda el frente y el tamaño, y el final se calcula como `(frente + tamaño) % capacidad`. Al llegar a la última casilla vuelve a la 0, así que nunca mueve elementos.
- **Llena:** `encolar` falla con `ColaLlenaError`. `agregar`, en cambio, pisa al más viejo y lo devuelve.

| Operación | Complejidad |
| --- | --- |
| `encolar(valor)`, `agregar(valor)`, `desencolar()` | O(1) |
| `ver_frente()`, `ver_final()`, `obtener(posicion)` | O(1) |
| `for` (del más viejo al más nuevo), `casillas()` (tal como están en memoria) | O(n) |

## Trie (árbol de prefijos)

- **Nodos:** cada nodo es una letra, y una palabra es el camino desde la raíz.
- **Hijos:** van en una lista enlazada de hermanos ordenada por letra ("primer hijo, siguiente hermano"). No hace falta un mapa, y los recorridos salen en orden alfabético.
- **Prefijos compartidos:** las palabras que empiezan igual comparten nodos.

| Operación | Complejidad |
| --- | --- |
| `insertar(palabra, valor)`, `buscar(palabra)`, `contiene(palabra)`, `hay_prefijo(prefijo)` | O(m·a): m letras, a hermanos por nivel; no depende de cuántas palabras haya |
| `con_prefijo(prefijo, limite)` | O(m·a + nodos visitados): recorre en profundidad con una `Pila` propia y para en el límite |
| `eliminar(palabra)` | O(m·a): poda los nodos que quedan sin uso |
| `tamanio()`, `cantidad_nodos()`, `raiz()` | O(1) |

