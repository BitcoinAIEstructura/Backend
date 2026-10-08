package com.bitcoinai.backend.simulacion;

import com.bitcoinai.backend.estructuras.Cola;
import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.estructuras.Pila;
import com.bitcoinai.backend.mercado.FuenteDeMercado;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.LongSupplier;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Libro de órdenes simulado (paper trading). Nunca toca una cuenta real.
 *
 * <p>Estructuras:
 * <ul>
 *   <li>{@code Cola<Orden>} de pendientes: se ejecutan en orden de llegada (FIFO).</li>
 *   <li>{@code Lista<Orden>} registro: órdenes ya ejecutadas, canceladas o rechazadas,
 *       en el orden en que terminaron.</li>
 *   <li>{@code Pila<Evento>} historial: el evento más reciente queda arriba.</li>
 *   <li>{@code Pila<Long>} con los ids en orden de creación, para deshacer la última.</li>
 * </ul>
 *
 * <p>Concurrencia: el bot y las peticiones HTTP lo usan desde hilos distintos.
 * Las estructuras no son sincronizadas; las protege un {@link ReentrantLock}
 * ({@code candado}), que se toma solo mientras se tocan y nunca durante una
 * llamada de red. Un segundo candado ({@code candadoProceso}) hace que las
 * órdenes se procesen de a una, así se respeta el orden FIFO aunque dos hilos
 * llamen a {@link #procesarSiguiente()} a la vez.
 *
 * <p>Tiempo real y persistencia (opcionales): avisa cada cambio a un
 * {@link PublicadorEventos} y guarda el estado en un {@link AlmacenSimulacion}
 * después de cada cambio. Ninguno de los dos depende de HTTP ni de archivos aquí.
 */
public class LibroDeOrdenes {

    /** Comisión por defecto: 0,1 %. */
    public static final double COMISION_POR_DEFECTO = 0.001;

    private final ReentrantLock candado = new ReentrantLock();
    private final ReentrantLock candadoProceso = new ReentrantLock();

    private final Cola<Orden> pendientes = new Cola<>();
    private final Lista<Orden> registro = new Lista<>();
    private final Pila<Evento> eventos = new Pila<>();
    private final Pila<Long> creadas = new Pila<>();

    /** Cuántos eventos del historial se guardan en disco como máximo (los más recientes). */
    public static final int EVENTOS_GUARDADOS_MAXIMO = 2000;

    private static final Logger LOG = Logger.getLogger(LibroDeOrdenes.class.getName());

    private Cartera cartera;
    private final FuenteDeMercado fuente;
    private final String simbolo;
    private final double comision;
    private final LongSupplier reloj;

    private long siguienteId = 1;
    private Orden enProceso;
    private volatile PublicadorEventos publicador = PublicadorEventos.NINGUNO;
    private AlmacenSimulacion almacen; // protegido por "candado"

    /**
     * Libro con comisión de 0,1 % y el reloj del sistema.
     *
     * @param cartera cartera simulada
     * @param fuente  de dónde sale el precio de ejecución
     * @param simbolo par, por ejemplo "BTCUSDT"
     */
    public LibroDeOrdenes(Cartera cartera, FuenteDeMercado fuente, String simbolo) {
        this(cartera, fuente, simbolo, COMISION_POR_DEFECTO, System::currentTimeMillis);
    }

    /**
     * Crea el libro.
     *
     * @param cartera  cartera simulada
     * @param fuente   de dónde sale el precio de ejecución
     * @param simbolo  par, por ejemplo "BTCUSDT"
     * @param comision comisión por operación, entre 0 y menos de 1
     * @param reloj    da el momento actual en ms (en pruebas, uno controlable)
     */
    public LibroDeOrdenes(Cartera cartera, FuenteDeMercado fuente, String simbolo, double comision, LongSupplier reloj) {
        this.cartera = Objects.requireNonNull(cartera, "cartera");
        this.fuente = Objects.requireNonNull(fuente, "fuente");
        this.simbolo = Objects.requireNonNull(simbolo, "simbolo");
        if (!(comision >= 0 && comision < 1)) {
            throw new IllegalArgumentException("La comisión debe estar entre 0 y 1: " + comision);
        }
        this.comision = comision;
        this.reloj = Objects.requireNonNull(reloj, "reloj");
    }

    // ---------- tiempo real y persistencia ----------

    /**
     * Indica a quién avisar de los cambios: "orden" cuando una orden cambia de
     * estado y "cartera" cuando cambia el saldo o el BTC.
     *
     * @param nuevoPublicador destino de los eventos
     */
    public void usarPublicador(PublicadorEventos nuevoPublicador) {
        this.publicador = Objects.requireNonNull(nuevoPublicador, "publicador");
    }

    /**
     * Carga el estado guardado (si hay) y a partir de ahora guarda después de
     * cada cambio. Reconstruye las estructuras en el mismo orden: la cola con el
     * orden de llegada, y las pilas con el elemento más reciente arriba.
     *
     * @param nuevoAlmacen dónde guardar y de dónde cargar
     * @return true si se recuperó un estado guardado
     */
    public boolean usarAlmacen(AlmacenSimulacion nuevoAlmacen) {
        Objects.requireNonNull(nuevoAlmacen, "almacen");
        Optional<EstadoSimulacion> guardado = nuevoAlmacen.cargar();
        candado.lock();
        try {
            guardado.ifPresent(this::restaurar);
            this.almacen = nuevoAlmacen;
            return guardado.isPresent();
        } finally {
            candado.unlock();
        }
    }

    /** Reemplaza el estado actual por el guardado. Se llama con el candado tomado. O(n). */
    private void restaurar(EstadoSimulacion estado) {
        if (estado.cartera() != null) {
            cartera = new Cartera(estado.cartera());
        }
        pendientes.vaciar();
        long mayorId = 0;
        for (Orden orden : estado.pendientes()) {
            pendientes.encolar(orden);           // la primera guardada vuelve a ser el frente
            mayorId = Math.max(mayorId, orden.id());
        }
        registro.vaciar();
        for (Orden orden : estado.registro()) {
            registro.agregar(orden);
            mayorId = Math.max(mayorId, orden.id());
        }
        creadas.vaciar();
        for (long id : estado.creadas()) {
            creadas.apilar(id);                  // la última guardada queda en el tope
        }
        eventos.vaciar();
        for (Evento evento : estado.eventos()) {
            eventos.apilar(evento);              // el evento más reciente queda arriba
        }
        siguienteId = Math.max(estado.siguienteId(), mayorId + 1);
    }

    /**
     * Arma la foto para guardar. Se llama con el candado tomado.
     * Complejidad: O(n), con n el total de órdenes y eventos.
     */
    private EstadoSimulacion instantanea() {
        Lista<Orden> listaPendientes = new Lista<>();
        if (enProceso != null) {
            // Si el servidor se apaga a mitad de un proceso, la orden vuelve al frente al recargar.
            listaPendientes.agregar(enProceso.conEstado(EstadoOrden.PENDIENTE, null));
        }
        int n = pendientes.tamanio();
        for (int i = 0; i < n; i++) {           // rotar la cola: queda igual tras n vueltas
            Orden orden = pendientes.desencolar();
            pendientes.encolar(orden);
            listaPendientes.agregar(orden);
        }
        Lista<Orden> listaRegistro = new Lista<>();
        for (Orden orden : registro) {
            listaRegistro.agregar(orden);
        }
        Lista<Evento> todos = deAbajoHaciaArriba(eventos);
        Lista<Evento> recientes = new Lista<>();
        int saltar = Math.max(0, todos.tamanio() - EVENTOS_GUARDADOS_MAXIMO);
        int i = 0;
        for (Evento evento : todos) {
            if (i++ >= saltar) {
                recientes.agregar(evento);
            }
        }
        return new EstadoSimulacion(cartera.datos(), siguienteId, listaPendientes, listaRegistro,
                deAbajoHaciaArriba(creadas), recientes);
    }

    /**
     * Elementos de una pila del fondo al tope, sin perderla: se desapila todo a
     * una auxiliar (que queda con el fondo arriba) y al devolverlos salen del
     * fondo al tope. Complejidad: O(n).
     */
    private static <T> Lista<T> deAbajoHaciaArriba(Pila<T> pila) {
        Pila<T> auxiliar = new Pila<>();
        while (!pila.estaVacia()) {
            auxiliar.apilar(pila.desapilar());
        }
        Lista<T> resultado = new Lista<>();
        while (!auxiliar.estaVacia()) {
            T elemento = auxiliar.desapilar();
            resultado.agregar(elemento);
            pila.apilar(elemento);
        }
        return resultado;
    }

    /** Guarda si hay almacén. Un fallo al guardar no deshace la operación: se registra y se sigue. */
    private void guardar() {
        if (almacen == null) {
            return;
        }
        try {
            almacen.guardar(instantanea());
        } catch (RuntimeException e) {
            LOG.log(Level.WARNING, "No se pudo guardar el estado de la simulación: " + e.getMessage(), e);
        }
    }

    // ---------- crear ----------

    /**
     * Crea una orden de compra por un monto en USDT.
     *
     * @param montoUsdt USDT a gastar (mayor que 0)
     * @param motivo    por qué se crea ("manual" si viene vacío)
     * @return la orden pendiente
     */
    public Orden crearCompra(double montoUsdt, String motivo) {
        return crearOrden(TipoOrden.COMPRA, montoUsdt, false, motivo);
    }

    /**
     * Crea una orden de venta por un monto en USDT.
     *
     * @param montoUsdt valor en USDT del BTC a vender (mayor que 0)
     * @param motivo    por qué se crea
     * @return la orden pendiente
     */
    public Orden crearVenta(double montoUsdt, String motivo) {
        return crearOrden(TipoOrden.VENTA, montoUsdt, false, motivo);
    }

    /**
     * Crea una orden de venta de todo el BTC que haya al ejecutarse.
     *
     * @param motivo por qué se crea
     * @return la orden pendiente
     */
    public Orden crearVentaTotal(String motivo) {
        return crearOrden(TipoOrden.VENTA, null, true, motivo);
    }

    /**
     * Crea una orden y la pone al final de la cola.
     * Complejidad: O(1).
     *
     * @param tipo   compra o venta
     * @param monto  USDT (mayor que 0); debe ser null si {@code todo} es true
     * @param todo   true para vender todo el BTC (solo con VENTA)
     * @param motivo por qué se crea ("manual" si viene vacío)
     * @return la orden pendiente
     * @throws IllegalArgumentException si la combinación de datos es inválida
     */
    public Orden crearOrden(TipoOrden tipo, Double monto, boolean todo, String motivo) {
        Objects.requireNonNull(tipo, "tipo");
        if (todo) {
            if (tipo != TipoOrden.VENTA || monto != null) {
                throw new IllegalArgumentException("'todo' solo se usa en ventas y sin monto");
            }
        } else if (monto == null || !(monto > 0) || Double.isInfinite(monto)) {
            throw new IllegalArgumentException("El monto debe ser un número mayor que 0");
        }
        String motivoFinal = (motivo == null || motivo.isBlank()) ? "manual" : motivo.trim();
        candado.lock();
        try {
            Orden orden = Orden.nueva(siguienteId++, tipo, monto, todo, reloj.getAsLong(), motivoFinal);
            pendientes.encolar(orden);
            creadas.apilar(orden.id());
            String que = todo ? "vender todo el BTC" : String.format(Locale.ROOT, "%.2f USDT", monto);
            apilarEvento(TipoEvento.ORDEN_CREADA, orden.id(),
                    "Orden #" + orden.id() + " de " + tipo + " por " + que + " creada (" + motivoFinal + ").");
            publicador.publicar("orden", orden);
            guardar();
            return orden;
        } finally {
            candado.unlock();
        }
    }

    // ---------- procesar ----------

    /**
     * Toma la orden del frente de la cola y la ejecuta al precio actual con
     * comisión, o la rechaza con el motivo si no alcanza el saldo o el BTC.
     *
     * <p>Pasos: (1) con el candado, saca la orden de la cola y la marca PROCESANDO;
     * (2) sin el candado, consulta el precio (puede tardar); (3) con el candado,
     * la ejecuta contra la cartera y la pasa al registro. Si el precio no se puede
     * obtener, la orden vuelve al frente de la cola, PENDIENTE, y se propaga el error.
     * Complejidad: O(1) más la consulta del precio (O(n) solo si hay que devolver la orden).
     *
     * @return la orden procesada, o vacío si no había pendientes
     * @throws com.bitcoinai.backend.mercado.MercadoException si falla la consulta del precio
     */
    public Optional<Orden> procesarSiguiente() {
        candadoProceso.lock();
        try {
            Orden pendiente;
            candado.lock();
            try {
                if (pendientes.estaVacia()) {
                    return Optional.empty();
                }
                pendiente = pendientes.desencolar();
                enProceso = pendiente.conEstado(EstadoOrden.PROCESANDO, null);
                publicador.publicar("orden", enProceso);
            } finally {
                candado.unlock();
            }

            double precio;
            try {
                precio = fuente.obtenerPrecioActual(simbolo);
            } catch (RuntimeException e) {
                candado.lock();
                try {
                    enProceso = null;
                    devolverAlFrente(pendiente);
                    publicador.publicar("orden", pendiente);
                    guardar();
                } finally {
                    candado.unlock();
                }
                throw e;
            }

            candado.lock();
            try {
                Orden resultado = ejecutar(enProceso, precio);
                enProceso = null;
                registro.agregar(resultado);
                publicador.publicar("orden", resultado);
                if (resultado.estado() == EstadoOrden.EJECUTADA) {
                    publicador.publicar("cartera", cartera.estado(precio));
                }
                guardar();
                return Optional.of(resultado);
            } finally {
                candado.unlock();
            }
        } finally {
            candadoProceso.unlock();
        }
    }

    /** Ejecuta (o rechaza) contra la cartera. Se llama con el candado tomado. */
    private Orden ejecutar(Orden orden, double precio) {
        long ahora = reloj.getAsLong();
        try {
            Cartera.Ejecucion ejecucion;
            if (orden.tipo() == TipoOrden.COMPRA) {
                ejecucion = cartera.comprar(orden.monto(), precio, comision);
            } else if (orden.todo()) {
                ejecucion = cartera.venderTodo(precio, comision);
            } else {
                ejecucion = cartera.vender(orden.monto(), precio, comision);
            }
            String detalle = String.format(Locale.ROOT, "%s %.8f BTC a %.2f por %.2f USDT (comisión %.2f USDT).",
                    orden.tipo() == TipoOrden.COMPRA ? "Compró" : "Vendió",
                    ejecucion.cantidadBtc(), precio, ejecucion.montoUsdt(), ejecucion.comision());
            apilarEvento(TipoEvento.ORDEN_EJECUTADA, orden.id(), "Orden #" + orden.id() + " ejecutada: " + detalle);
            return orden.ejecutada(ahora, precio, ejecucion, detalle);
        } catch (OperacionRechazadaException e) {
            apilarEvento(TipoEvento.ORDEN_RECHAZADA, orden.id(), "Orden #" + orden.id() + " rechazada: " + e.getMessage() + ".");
            return orden.rechazada(ahora, precio, e.getMessage());
        }
    }

    /**
     * Vuelve a poner una orden al frente de la cola. Una cola solo agrega al final,
     * así que se arma una nueva con esa orden primero y luego las demás.
     * Complejidad: O(n).
     */
    private void devolverAlFrente(Orden orden) {
        Cola<Orden> resto = new Cola<>();
        while (!pendientes.estaVacia()) {
            resto.encolar(pendientes.desencolar());
        }
        pendientes.encolar(orden);
        while (!resto.estaVacia()) {
            pendientes.encolar(resto.desencolar());
        }
    }

    // ---------- cancelar y deshacer ----------

    /**
     * Cancela una orden pendiente.
     *
     * <p>Una cola no permite sacar un elemento del medio, así que se reconstruye:
     * se desencolan todas las órdenes y se vuelven a encolar todas menos la
     * cancelada. Las demás conservan su orden. Complejidad: O(n), con n pendientes.
     *
     * @param id id de la orden
     * @return la orden cancelada
     * @throws OrdenNoEncontradaException si no existe
     * @throws OperacionInvalidaException si ya no está pendiente
     */
    public Orden cancelar(long id) {
        candado.lock();
        try {
            Orden cancelada = quitarDeLaCola(id, EstadoOrden.CANCELADA, "Cancelada antes de ejecutarse.");
            if (cancelada == null) {
                throw noPendiente(id);
            }
            apilarEvento(TipoEvento.ORDEN_CANCELADA, id, "Orden #" + id + " cancelada.");
            publicador.publicar("orden", cancelada);
            guardar();
            return cancelada;
        } finally {
            candado.unlock();
        }
    }

    /**
     * Deshace la última orden creada si sigue pendiente.
     *
     * <p>Los ids se apilan al crearse, así que el tope de la pila es la última
     * creada. Se desapila: si sigue pendiente se quita de la cola (O(n)); si no,
     * no se hace nada. Llamarlo de nuevo intenta con la anterior.
     *
     * @return la orden deshecha, o vacío si no había ninguna o ya no estaba pendiente
     */
    public Optional<Orden> deshacerUltimaOrden() {
        candado.lock();
        try {
            if (creadas.estaVacia()) {
                return Optional.empty();
            }
            long id = creadas.desapilar();
            Orden deshecha = quitarDeLaCola(id, EstadoOrden.CANCELADA, "Deshecha: era la última orden creada.");
            if (deshecha == null) {
                guardar(); // la pila de creadas cambió
                return Optional.empty();
            }
            apilarEvento(TipoEvento.ORDEN_DESHECHA, id, "Orden #" + id + " deshecha.");
            publicador.publicar("orden", deshecha);
            guardar();
            return Optional.of(deshecha);
        } finally {
            candado.unlock();
        }
    }

    /**
     * Reconstruye la cola sin la orden {@code id}; si estaba, la pasa al registro
     * con el estado dado y la devuelve. Se llama con el candado tomado. O(n).
     */
    private Orden quitarDeLaCola(long id, EstadoOrden estado, String detalle) {
        Orden quitada = null;
        int n = pendientes.tamanio();
        for (int i = 0; i < n; i++) {
            Orden orden = pendientes.desencolar();
            if (orden.id() == id && quitada == null) {
                quitada = orden.conEstado(estado, detalle);
            } else {
                pendientes.encolar(orden);
            }
        }
        if (quitada != null) {
            registro.agregar(quitada);
        }
        return quitada;
    }

    private RuntimeException noPendiente(long id) {
        if (enProceso != null && enProceso.id() == id) {
            return new OperacionInvalidaException("La orden #" + id + " se está procesando y ya no se puede cancelar");
        }
        int indice = registro.buscar(o -> o.id() == id);
        if (indice >= 0) {
            return new OperacionInvalidaException("La orden #" + id + " ya no está pendiente: está "
                    + registro.obtener(indice).estado());
        }
        return new OrdenNoEncontradaException(id);
    }

    // ---------- consultas ----------

    /**
     * Devuelve las órdenes, opcionalmente filtradas por estado: primero las
     * pendientes en orden de cola, luego la que se está procesando y por último
     * el registro.
     *
     * <p>Para leer la cola sin perderla, se desencola cada orden y se vuelve a
     * encolar: tras n vueltas queda igual que antes. Complejidad: O(n + r).
     *
     * @param estado estado a filtrar, o null para todas
     * @return una lista nueva
     */
    public Lista<Orden> ordenes(EstadoOrden estado) {
        candado.lock();
        try {
            Lista<Orden> resultado = new Lista<>();
            int n = pendientes.tamanio();
            for (int i = 0; i < n; i++) {
                Orden orden = pendientes.desencolar();
                pendientes.encolar(orden);
                if (estado == null || orden.estado() == estado) {
                    resultado.agregar(orden);
                }
            }
            if (enProceso != null && (estado == null || estado == EstadoOrden.PROCESANDO)) {
                resultado.agregar(enProceso);
            }
            for (Orden orden : registro) {
                if (estado == null || orden.estado() == estado) {
                    resultado.agregar(orden);
                }
            }
            return resultado;
        } finally {
            candado.unlock();
        }
    }

    /**
     * Busca una orden por id.
     * Complejidad: O(n + r).
     *
     * @param id id de la orden
     * @return la orden en su estado actual
     * @throws OrdenNoEncontradaException si no existe
     */
    public Orden obtener(long id) {
        for (Orden orden : ordenes(null)) {
            if (orden.id() == id) {
                return orden;
            }
        }
        throw new OrdenNoEncontradaException(id);
    }

    /**
     * Devuelve cuántas órdenes esperan en la cola.
     * Complejidad: O(1).
     *
     * @return el tamaño de la cola
     */
    public int cantidadPendientes() {
        candado.lock();
        try {
            return pendientes.tamanio();
        } finally {
            candado.unlock();
        }
    }

    /**
     * Devuelve los eventos más recientes, del más nuevo al más viejo, sin
     * quitarlos del historial.
     *
     * <p>Una pila solo deja ver el tope: se desapilan los k primeros (guardándolos
     * en el resultado y en una pila auxiliar) y después se devuelven desde la
     * auxiliar, que los deja en el mismo orden de antes. Complejidad: O(k).
     *
     * @param limite cuántos eventos devolver como máximo (0 o más)
     * @return una lista nueva
     */
    public Lista<Evento> historial(int limite) {
        if (limite < 0) {
            throw new IllegalArgumentException("El límite no puede ser negativo");
        }
        candado.lock();
        try {
            Lista<Evento> resultado = new Lista<>();
            Pila<Evento> auxiliar = new Pila<>();
            while (!eventos.estaVacia() && resultado.tamanio() < limite) {
                Evento evento = eventos.desapilar();
                resultado.agregar(evento);
                auxiliar.apilar(evento);
            }
            while (!auxiliar.estaVacia()) {
                eventos.apilar(auxiliar.desapilar());
            }
            return resultado;
        } finally {
            candado.unlock();
        }
    }

    /**
     * Devuelve la cartera valorada al precio dado.
     *
     * @param precio precio de 1 BTC
     * @return foto de la cartera
     */
    public EstadoCartera estadoCartera(double precio) {
        candado.lock();
        try {
            return cartera.estado(precio);
        } finally {
            candado.unlock();
        }
    }

    /**
     * Devuelve la cartera valorada al precio actual (consulta la fuente fuera del candado).
     *
     * @return foto de la cartera
     */
    public EstadoCartera estadoCartera() {
        return estadoCartera(fuente.obtenerPrecioActual(simbolo));
    }

    /**
     * Agrega un evento al historial (lo usa el bot para sus decisiones).
     *
     * @param tipo        tipo de evento
     * @param idOrden     orden relacionada, o null
     * @param descripcion una frase en español
     */
    public void registrarEvento(TipoEvento tipo, Long idOrden, String descripcion) {
        candado.lock();
        try {
            apilarEvento(tipo, idOrden, descripcion);
            guardar();
        } finally {
            candado.unlock();
        }
    }

    /** Se llama con el candado tomado. O(1). */
    private void apilarEvento(TipoEvento tipo, Long idOrden, String descripcion) {
        eventos.apilar(new Evento(reloj.getAsLong(), tipo, idOrden, descripcion));
    }
}
