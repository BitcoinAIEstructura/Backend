package com.bitcoinai.backend.api;

import com.bitcoinai.backend.estrategia.Backtester;
import com.bitcoinai.backend.estrategia.Decision;
import com.bitcoinai.backend.estrategia.Estrategia;
import com.bitcoinai.backend.estrategia.FabricaEstrategias;
import com.bitcoinai.backend.estrategia.Pronostico;
import com.bitcoinai.backend.estrategia.ValidacionEntrenamientoPrueba;
import com.bitcoinai.backend.estructuras.ListaDoble;
import com.bitcoinai.backend.indicadores.FabricaIndicadores;
import com.bitcoinai.backend.indicadores.Indicador;
import com.bitcoinai.backend.indicadores.MaximaCaida;
import com.bitcoinai.backend.mercado.FuenteDeMercado;
import com.bitcoinai.backend.mercado.VelasCerradas;
import com.bitcoinai.backend.modelo.Intervalo;
import com.bitcoinai.backend.modelo.Vela;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Endpoints de la API y su registro en el {@link Router}.
 *
 * <ul>
 *   <li>{@code GET /health}</li>
 *   <li>{@code GET /api/precio}</li>
 *   <li>{@code GET /api/velas?intervalo=1d&cantidad=200}</li>
 *   <li>{@code GET /api/indicadores?indicador=rsi&periodo=14&intervalo=1d&cantidad=200}</li>
 *   <li>{@code GET /api/senal?estrategia=combinada&intervalo=1d}</li>
 *   <li>{@code GET /api/backtest?estrategia=cruce&capital=1000&comision=0.001&intervalo=1d&cantidad=1000}</li>
 * </ul>
 */
public class RutasApi {

    /** Máximo de velas que se aceptan en /api/velas. */
    public static final int CANTIDAD_MAXIMA = 1000;

    private static final String INTERVALO_POR_DEFECTO = "1d";
    private static final int CANTIDAD_POR_DEFECTO = 200;

    private final FuenteDeMercado fuente;
    private final String simbolo;

    /**
     * Crea los endpoints.
     *
     * @param fuente  de dónde salen los datos de mercado
     * @param simbolo par que se consulta, por ejemplo "BTCUSDT"
     */
    public RutasApi(FuenteDeMercado fuente, String simbolo) {
        this.fuente = Objects.requireNonNull(fuente, "fuente");
        this.simbolo = Objects.requireNonNull(simbolo, "simbolo");
    }

    /**
     * Crea un enrutador con todos los endpoints registrados.
     *
     * @return el enrutador
     */
    public Router crearRouter() {
        return new Router()
                .get("/health", this::salud)
                .get("/api/precio", this::precio)
                .get("/api/velas", this::velas)
                .get("/api/indicadores", this::indicadores)
                .get("/api/senal", this::senal)
                .get("/api/backtest", this::backtest);
    }

    /** Responde siempre rápido y sin consultar la fuente de mercado. */
    private Respuesta salud(Peticion peticion) {
        return Respuesta.ok(Map.of("estado", "ok"));
    }

    private Respuesta precio(Peticion peticion) {
        double precio = fuente.obtenerPrecioActual(simbolo);
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("simbolo", simbolo);
        cuerpo.put("precio", precio);
        cuerpo.put("momento", System.currentTimeMillis());
        return Respuesta.ok(cuerpo);
    }

    private Respuesta velas(Peticion peticion) {
        Intervalo intervalo = leerIntervalo(peticion.parametro("intervalo", INTERVALO_POR_DEFECTO));
        int cantidad = leerCantidad(peticion.parametro("cantidad", String.valueOf(CANTIDAD_POR_DEFECTO)));
        ListaDoble<Vela> velas = fuente.obtenerVelas(simbolo, intervalo, cantidad);

        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("simbolo", simbolo);
        cuerpo.put("intervalo", intervalo.codigo());
        cuerpo.put("cantidad", velas.tamanio());
        cuerpo.put("velas", velas);
        return Respuesta.ok(cuerpo);
    }

    /** Valida todos los parámetros antes de consultar la fuente, para no gastar peticiones en un 400. */
    private Respuesta indicadores(Peticion peticion) {
        Indicador indicador;
        try {
            indicador = FabricaIndicadores.crear(peticion.parametros().get("indicador"), peticion.parametros());
        } catch (IllegalArgumentException e) {
            throw new ApiException(400, e.getMessage());
        }
        Intervalo intervalo = leerIntervalo(peticion.parametro("intervalo", INTERVALO_POR_DEFECTO));
        int cantidad = leerCantidad(peticion.parametro("cantidad", String.valueOf(CANTIDAD_POR_DEFECTO)));
        ListaDoble<Vela> velas = fuente.obtenerVelas(simbolo, intervalo, cantidad);

        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("simbolo", simbolo);
        cuerpo.put("intervalo", intervalo.codigo());
        cuerpo.put("indicador", indicador.nombre());
        cuerpo.put("parametros", indicador.parametros());
        cuerpo.put("series", indicador.calcularSeries(velas));
        cuerpo.put("maximaCaida", MaximaCaida.deVelas(velas));
        cuerpo.put("cantidad", velas.tamanio());
        cuerpo.put("velas", velas);
        return Respuesta.ok(cuerpo);
    }

    /** Decisión y pronóstico más recientes, con las velas ya cerradas. */
    private Respuesta senal(Peticion peticion) {
        Estrategia estrategia = leerEstrategia(peticion);
        Intervalo intervalo = leerIntervalo(peticion.parametro("intervalo", INTERVALO_POR_DEFECTO));
        int cantidad = leerCantidad(peticion.parametro("cantidad", String.valueOf(CANTIDAD_POR_DEFECTO)));
        ListaDoble<Vela> velas = soloCerradas(fuente.obtenerVelas(simbolo, intervalo, cantidad));

        Decision decision = estrategia.evaluar(velas);
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("simbolo", simbolo);
        cuerpo.put("intervalo", intervalo.codigo());
        cuerpo.put("estrategia", estrategia.nombre());
        cuerpo.put("parametros", estrategia.parametros());
        cuerpo.put("velasAnalizadas", velas.tamanio());
        cuerpo.put("decision", decision);
        cuerpo.put("pronostico", Pronostico.desde(estrategia, velas, decision));
        return Respuesta.ok(cuerpo);
    }

    /** Backtest con los parámetros pedidos sobre todo el periodo, más la validación 70/30. */
    private Respuesta backtest(Peticion peticion) {
        Estrategia estrategia = leerEstrategia(peticion);
        double capital = leerDecimal(peticion, "capital", 1000, 1, 1_000_000_000, "1 y 1000000000");
        double comision = leerDecimal(peticion, "comision", 0.001, 0, 0.05, "0 y 0.05");
        double entrenamiento = leerDecimal(peticion, "entrenamiento",
                ValidacionEntrenamientoPrueba.FRACCION_POR_DEFECTO, 0.5, 0.9, "0.5 y 0.9");
        Intervalo intervalo = leerIntervalo(peticion.parametro("intervalo", INTERVALO_POR_DEFECTO));
        int cantidad = leerCantidad(peticion.parametro("cantidad", String.valueOf(CANTIDAD_MAXIMA)));
        ListaDoble<Vela> velas = soloCerradas(fuente.obtenerVelas(simbolo, intervalo, cantidad));

        Backtester backtester = new Backtester(capital, comision);
        Map<String, Object> cuerpo = new LinkedHashMap<>();
        cuerpo.put("simbolo", simbolo);
        cuerpo.put("intervalo", intervalo.codigo());
        cuerpo.put("estrategia", estrategia.nombre());
        cuerpo.put("parametros", estrategia.parametros());
        cuerpo.put("resultado", backtester.ejecutar(estrategia, velas));
        cuerpo.put("validacion", new ValidacionEntrenamientoPrueba(backtester, entrenamiento)
                .ejecutar(FabricaEstrategias.candidatos(estrategia.nombre()), velas));
        cuerpo.put("aviso", Pronostico.AVISO);
        return Respuesta.ok(cuerpo);
    }

    private static Estrategia leerEstrategia(Peticion peticion) {
        try {
            return FabricaEstrategias.crear(peticion.parametro("estrategia", "combinada"), peticion.parametros());
        } catch (IllegalArgumentException e) {
            throw new ApiException(400, e.getMessage());
        }
    }

    private static double leerDecimal(Peticion peticion, String nombre, double porDefecto,
                                      double minimo, double maximo, String rango) {
        String texto = peticion.parametro(nombre, null);
        if (texto == null) {
            return porDefecto;
        }
        try {
            double valor = Double.parseDouble(texto.trim());
            if (valor >= minimo && valor <= maximo) {
                return valor;
            }
        } catch (NumberFormatException e) {
            // cae al error de abajo
        }
        throw new ApiException(400, "Parámetro '" + nombre + "' inválido: '" + texto
                + "'. Debe ser un número entre " + rango);
    }

    private static ListaDoble<Vela> soloCerradas(ListaDoble<Vela> velas) {
        return VelasCerradas.filtrar(velas, System.currentTimeMillis());
    }

    private static Intervalo leerIntervalo(String texto) {
        try {
            return Intervalo.desdeCodigo(texto);
        } catch (IllegalArgumentException e) {
            throw new ApiException(400, "Parámetro 'intervalo' inválido: '" + texto
                    + "'. Valores permitidos: 1m, 5m, 15m, 1h, 4h, 1d");
        }
    }

    private static int leerCantidad(String texto) {
        try {
            int cantidad = Integer.parseInt(texto.trim());
            if (cantidad >= 1 && cantidad <= CANTIDAD_MAXIMA) {
                return cantidad;
            }
        } catch (NumberFormatException e) {
            // cae al error de abajo
        }
        throw new ApiException(400, "Parámetro 'cantidad' inválido: '" + texto
                + "'. Debe ser un número entero entre 1 y " + CANTIDAD_MAXIMA);
    }
}
