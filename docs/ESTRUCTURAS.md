# Estructuras de datos

Todas están en `com.bitcoinai.backend.estructuras`, son genéricas (`<T>`) y están hechas a mano con nodos enlazados (`NodoSimple` y `NodoDoble`), sin colecciones del JDK por dentro. Siempre se lleva un contador, así que `tamanio()` y `estaVacia()` cuestan O(1). Si se lee o se quita algo de una estructura vacía, se lanza `EstructuraVaciaException`; si se usa un índice inválido, `IndiceFueraDeRangoException`.

## Uso en el proyecto

| Estructura | Uso |
| --- | --- |
| `ListaDoble` | Ventana de velas: las nuevas entran por el final, las más antiguas salen por el inicio con `conservarUltimos(n)`, y los indicadores la recorren en los dos sentidos. |
| `Cola` | Órdenes pendientes: se ejecutan en el mismo orden en que llegaron (FIFO). |
| `Pila` | Historial de decisiones: la decisión más reciente queda arriba (LIFO). |
| `Lista` | Operaciones cerradas: se agregan al final y se recorren para calcular métricas. |

### Dónde está cada uso en el código

| Estructura | Clase | Para qué |
| --- | --- | --- |
| `ListaDoble<Vela>` | `ClienteBinance` | Junta los lotes de velas: recorre cada lote con `iteradorAtras()` y agrega al inicio, descartando duplicados |
| `ListaDoble<Double>` | `Sma`, `BandasBollinger`, `Volatilidad` | Ventana deslizante con `conservarUltimos(p)`: O(n) en total |
| `ListaDoble<T>` | `Series.ultimos` | Toma los n valores más recientes empezando por la cola: O(n) y no O(tamaño total) |
| `ListaDoble<Vela>` | `Backtester` | Velas "hasta ahora": se agrega una al final por vuelta, así la estrategia nunca ve el futuro |
| `ListaDoble<Vela>` | `VelasCerradas` | Quita la vela en curso con `eliminarUltimo()`, O(1) |
| `Pila<Decision>` | `Backtester` | Historial de decisiones; al desapilar salen de la más nueva a la más vieja |
| `Lista<OperacionCerrada>` | `Backtester` | Operaciones del backtest, en orden |
| `Cola<Orden>` | `LibroDeOrdenes` | Órdenes pendientes, FIFO |
| `Lista<Orden>` | `LibroDeOrdenes` | Registro de órdenes ejecutadas, canceladas y rechazadas |
| `Pila<Evento>` | `LibroDeOrdenes` | Historial de eventos, el más reciente arriba |
| `Pila<Long>` | `LibroDeOrdenes` | Ids en orden de creación, para deshacer la última orden (y la anterior, y la anterior…) |
| `ListaDoble<Suscriptor>` | `Publicador` | Clientes conectados a `/api/stream`; cada uno guarda su nodo para quitarlo en O(1) al desconectarse |

### Quitar un elemento por su nodo en O(1) (tiempo real)

El `Publicador` guarda los clientes de `/api/stream` en una `ListaDoble<Suscriptor>`. Al conectarse un cliente se lo agrega con `agregarFinalNodo(suscriptor)`, que devuelve el nodo, y el suscriptor lo guarda. Cuando el cliente se desconecta, se llama a `eliminarNodo(nodo)`:

- **Por qué es O(1):** el nodo ya conoce a su anterior y a su siguiente, así que basta con unirlos entre sí (y mover la cabeza o la cola si era un extremo). No hay que recorrer la lista para buscarlo.
- **Comparación:** en una lista simple habría que recorrerla para encontrar el nodo anterior, O(n). Buscar por valor también sería O(n).
- **Seguridad:** cada nodo recuerda a qué lista pertenece. Quitarlo dos veces, o pasar un nodo de otra lista o de antes de un `vaciar()`, devuelve `false` en vez de romper la estructura.

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
| `agregar(T)` | O(1) | Usa la referencia a la cola |
| `agregarInicio(T)` | O(1) | |
| `insertarOrdenado(T, Comparator)` | O(n) | Recorre hasta la posición; estable con iguales |
| `obtener(int)` | O(n) | O(1) para el primero y el último |
| `eliminar(int)` | O(n) | Hay que llegar al nodo anterior; O(1) para el primero |
| `buscar(Predicate)` | O(n) | Devuelve el índice o -1 |
| `primero()`, `ultimo()` | O(1) | |
| `tamanio()`, `estaVacia()`, `vaciar()` | O(1) | |
| Recorrido con for-each | O(n) | |

## ListaDoble (doblemente enlazada, con cabeza y cola)

| Operación | Complejidad | Nota |
| --- | --- | --- |
| `agregarInicio(T)`, `agregarFinal(T)` | O(1) | |
| `agregarFinalNodo(T)` | O(1) | Igual que `agregarFinal`, pero devuelve el nodo |
| `eliminarNodo(NodoDoble)` | O(1) | Quita ese nodo sin recorrer la lista; `false` si no pertenece |
| `insertar(int, T)` | O(min(i, n − i)) | Llega desde el extremo más cercano |
| `obtener(int)` | O(min(i, n − i)) | Peor caso O(n/2) |
| `eliminarPrimero()`, `eliminarUltimo()` | O(1) | Cada nodo conoce a su anterior |
| `eliminar(int)` | O(min(i, n − i)) | Llegar al nodo; desenlazarlo es O(1) |
| `primero()`, `ultimo()` | O(1) | |
| `conservarUltimos(n)` | O(k) | k = elementos descartados |
| `tamanio()`, `estaVacia()`, `vaciar()` | O(1) | |
| `iteradorAdelante()`, `iteradorAtras()`, for-each | O(n) | Crear el iterador es O(1); cada paso es O(1) |

## Cola (FIFO, con frente y final)

| Operación | Complejidad |
| --- | --- |
| `encolar(T)` | O(1) |
| `desencolar()` | O(1) |
| `verFrente()` | O(1) |
| `tamanio()`, `estaVacia()`, `vaciar()` | O(1) |

## Pila (LIFO, con tope)

| Operación | Complejidad |
| --- | --- |
| `apilar(T)` | O(1) |
| `desapilar()` | O(1) |
| `verTope()` | O(1) |
| `tamanio()`, `estaVacia()`, `vaciar()` | O(1) |
