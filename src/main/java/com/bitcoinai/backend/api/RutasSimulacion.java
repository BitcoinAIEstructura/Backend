package com.bitcoinai.backend.api;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.simulacion.BotSimulado;
import com.bitcoinai.backend.simulacion.ConfiguracionBot;
import com.bitcoinai.backend.simulacion.EstadoOrden;
import com.bitcoinai.backend.simulacion.LibroDeOrdenes;
import com.bitcoinai.backend.simulacion.OperacionInvalidaException;
import com.bitcoinai.backend.simulacion.Orden;
import com.bitcoinai.backend.simulacion.OrdenNoEncontradaException;
import com.bitcoinai.backend.simulacion.TipoOrden;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Supplier;

/**
 * Endpoints de la simulación de operaciones (paper trading). Nunca operan con
 * dinero real.
 *
 * <ul>
 *   <li>{@code POST /api/ordenes}, {@code GET /api/ordenes?estado=PENDIENTE}</li>
 *   <li>{@code GET /api/ordenes/{id}}, {@code DELETE /api/ordenes/{id}}</li>
 *   <li>{@code POST /api/ordenes/procesar}, {@code POST /api/ordenes/deshacer}</li>
 *   <li>{@code GET /api/cartera}, {@code GET /api/historial?limite=50}</li>
 *   <li>{@code POST /api/bot/iniciar}, {@code POST /api/bot/detener}, {@code GET /api/bot/estado}</li>
 * </ul>
 * Errores del dominio: orden inexistente → 404; operación que el estado no
 * permite (cancelar algo ya ejecutado, procesar con la cola vacía, iniciar el
 * bot dos veces) → 409; datos inválidos → 400.
 */
public class RutasSimulacion {

    /** Monto máximo de una orden, en USDT. */
    public static final double MONTO_MAXIMO = 1_000_000_000;

    private static final int LIMITE_HISTORIAL_POR_DEFECTO = 50;
    private static final int LIMITE_HISTORIAL_MAXIMO = 500;

    private final LibroDeOrdenes libro;
    private final BotSimulado bot;

    /**
     * Crea los endpoints.
     *
     * @param libro libro de órdenes compartido con el bot
     * @param bot   bot simulado
     */
    public RutasSimulacion(LibroDeOrdenes libro, BotSimulado bot) {
        this.libro = Objects.requireNonNull(libro, "libro");
        this.bot = Objects.requireNonNull(bot, "bot");
    }

    /**
     * Registra los endpoints en un enrutador.
     *
     * @param router enrutador donde registrarlos
     * @return el mismo enrutador
     */
    public Router registrar(Router router) {
        return router
                .post("/api/ordenes", this::crear)
                .get("/api/ordenes", this::listar)
                .post("/api/ordenes/procesar", this::procesar)
                .post("/api/ordenes/deshacer", this::deshacer)
                .get("/api/ordenes/{id}", this::obtener)
                .delete("/api/ordenes/{id}", this::cancelar)
                .get("/api/cartera", p -> Respuesta.ok(libro.estadoCartera()))
                .get("/api/historial", this::historial)
                .post("/api/bot/iniciar", this::iniciarBot)
                .post("/api/bot/detener", p -> Respuesta.ok(bot.detener()))
                .get("/api/bot/estado", p -> Respuesta.ok(bot.estado()));
    }

    // ---------- órdenes ----------

    /** Cuerpo: {"tipo":"COMPRA","monto":500}, {"tipo":"VENTA","monto":200} o {"tipo":"VENTA","todo":true}; "motivo" es opcional. */
    private Respuesta crear(Peticion peticion) {
        Map<String, Object> cuerpo = peticion.cuerpoJson();
        TipoOrden tipo = leerTipo(cuerpo.get("tipo"));
        Object todoCrudo = cuerpo.get("todo");
        if (todoCrudo != null && !(todoCrudo instanceof Boolean)) {
            throw new ApiException(400, "El campo 'todo' debe ser true o false");
        }
        boolean todo = Boolean.TRUE.equals(todoCrudo);
        Object montoCrudo = cuerpo.get("monto");
        Double monto = null;
        if (todo) {
            if (tipo != TipoOrden.VENTA) {
                throw new ApiException(400, "El campo 'todo' solo se usa en órdenes de VENTA");
            }
            if (montoCrudo != null) {
                throw new ApiException(400, "Con 'todo': true no se indica 'monto'");
            }
        } else {
            monto = leerMonto(montoCrudo);
        }
        Object motivo = cuerpo.get("motivo");
        if (motivo != null && !(motivo instanceof String)) {
            throw new ApiException(400, "El campo 'motivo' debe ser un texto");
        }
        Orden orden = libro.crearOrden(tipo, monto, todo, (String) motivo);
        return new Respuesta(201, orden);
    }

    private Respuesta listar(Peticion peticion) {
        String texto = peticion.parametro("estado", null);
        EstadoOrden estado = null;
        if (texto != null) {
            try {
                estado = EstadoOrden.valueOf(texto.trim().toUpperCase(Locale.ROOT));
            } catch (IllegalArgumentException e) {
                throw new ApiException(400, "Parámetro 'estado' inválido: '" + texto
                        + "'. Valores permitidos: PENDIENTE, PROCESANDO, EJECUTADA, CANCELADA, RECHAZADA");
            }
        }
        Lista<Orden> ordenes = libro.ordenes(estado);
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("cantidad", ordenes.tamanio());
        cuerpo.put("ordenes", ordenes);
        return Respuesta.ok(cuerpo);
    }

    private Respuesta obtener(Peticion peticion) {
        long id = leerId(peticion);
        return Respuesta.ok(traducirErrores(() -> libro.obtener(id)));
    }

    private Respuesta cancelar(Peticion peticion) {
        long id = leerId(peticion);
        return Respuesta.ok(traducirErrores(() -> libro.cancelar(id)));
    }

    private Respuesta procesar(Peticion peticion) {
        Optional<Orden> orden = libro.procesarSiguiente();
        if (orden.isEmpty()) {
            throw new ApiException(409, "No hay órdenes pendientes para procesar");
        }
        return Respuesta.ok(orden.get());
    }

    private Respuesta deshacer(Peticion peticion) {
        Optional<Orden> orden = libro.deshacerUltimaOrden();
        if (orden.isEmpty()) {
            throw new ApiException(409, "No hay una orden reciente pendiente que deshacer");
        }
        return Respuesta.ok(orden.get());
    }

    private Respuesta historial(Peticion peticion) {
        String texto = peticion.parametro("limite", String.valueOf(LIMITE_HISTORIAL_POR_DEFECTO));
        int limite;
        try {
            limite = Integer.parseInt(texto.trim());
        } catch (NumberFormatException e) {
            limite = -1;
        }
        if (limite < 1 || limite > LIMITE_HISTORIAL_MAXIMO) {
            throw new ApiException(400, "Parámetro 'limite' inválido: '" + texto
                    + "'. Debe ser un número entero entre 1 y " + LIMITE_HISTORIAL_MAXIMO);
        }
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("eventos", libro.historial(limite));
        return Respuesta.ok(cuerpo);
    }

    // ---------- bot ----------

    /** Cuerpo opcional con cualquier campo de {@link ConfiguracionBot}; los que falten toman el valor por defecto. */
    private Respuesta iniciarBot(Peticion peticion) {
        Map<String, Object> cuerpo = peticion.cuerpoJsonOpcional();
        ConfiguracionBot porDefecto = ConfiguracionBot.porDefecto();
        ConfiguracionBot configuracion;
        try {
            configuracion = new ConfiguracionBot(
                    (int) numero(cuerpo, "segundosEntreCiclos", porDefecto.segundosEntreCiclos(), true),
                    texto(cuerpo, "intervalo", porDefecto.intervalo()),
                    (int) numero(cuerpo, "cantidadVelas", porDefecto.cantidadVelas(), true),
                    numero(cuerpo, "riesgo", porDefecto.riesgo(), false),
                    numero(cuerpo, "stopLoss", porDefecto.stopLoss(), false),
                    numero(cuerpo, "takeProfit", porDefecto.takeProfit(), false));
        } catch (IllegalArgumentException e) {
            throw new ApiException(400, e.getMessage());
        }
        try {
            return Respuesta.ok(bot.iniciar(configuracion));
        } catch (IllegalStateException e) {
            throw new ApiException(409, e.getMessage());
        }
    }

    // ---------- lectura y validación ----------

    private static TipoOrden leerTipo(Object valor) {
        if (!(valor instanceof String texto)) {
            throw new ApiException(400, "Falta el campo 'tipo' (COMPRA o VENTA)");
        }
        try {
            return TipoOrden.valueOf(texto.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            throw new ApiException(400, "Campo 'tipo' inválido: '" + texto + "'. Valores permitidos: COMPRA, VENTA");
        }
    }

    private static double leerMonto(Object valor) {
        if (valor == null) {
            throw new ApiException(400, "Falta el campo 'monto' (USDT, mayor que 0)");
        }
        if (!(valor instanceof Double monto)) {
            throw new ApiException(400, "El campo 'monto' debe ser un número, no " + valor.getClass().getSimpleName());
        }
        if (!(monto > 0) || monto > MONTO_MAXIMO) {
            throw new ApiException(400, "El campo 'monto' debe ser mayor que 0 y como máximo " + (long) MONTO_MAXIMO);
        }
        return monto;
    }

    private static long leerId(Peticion peticion) {
        String texto = peticion.parametroRuta("id");
        try {
            long id = Long.parseLong(texto);
            if (id > 0) {
                return id;
            }
        } catch (NumberFormatException e) {
            // cae al error de abajo
        }
        throw new ApiException(400, "Id de orden inválido: '" + texto + "'. Debe ser un número entero positivo");
    }

    private static double numero(Map<String, Object> cuerpo, String campo, double porDefecto, boolean entero) {
        Object valor = cuerpo.get(campo);
        if (valor == null) {
            return porDefecto;
        }
        if (!(valor instanceof Double numero) || (entero && numero != Math.rint(numero))) {
            throw new ApiException(400, "El campo '" + campo + "' debe ser un número" + (entero ? " entero" : ""));
        }
        return numero;
    }

    private static String texto(Map<String, Object> cuerpo, String campo, String porDefecto) {
        Object valor = cuerpo.get(campo);
        if (valor == null) {
            return porDefecto;
        }
        if (!(valor instanceof String texto)) {
            throw new ApiException(400, "El campo '" + campo + "' debe ser un texto");
        }
        return texto;
    }

    private static <T> T traducirErrores(Supplier<T> operacion) {
        try {
            return operacion.get();
        } catch (OrdenNoEncontradaException e) {
            throw new ApiException(404, e.getMessage());
        } catch (OperacionInvalidaException e) {
            throw new ApiException(409, e.getMessage());
        }
    }
}
