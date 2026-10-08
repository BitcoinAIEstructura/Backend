package com.bitcoinai.backend;

import com.bitcoinai.backend.api.Configuracion;
import com.bitcoinai.backend.api.Publicador;
import com.bitcoinai.backend.api.Router;
import com.bitcoinai.backend.api.RutasApi;
import com.bitcoinai.backend.api.RutasSimulacion;
import com.bitcoinai.backend.api.Servidor;
import com.bitcoinai.backend.estrategia.EstrategiaCombinada;
import com.bitcoinai.backend.mercado.CacheMercado;
import com.bitcoinai.backend.mercado.ClienteBinance;
import com.bitcoinai.backend.mercado.FuenteDeMercado;
import com.bitcoinai.backend.persistencia.AlmacenArchivos;
import com.bitcoinai.backend.simulacion.BotSimulado;
import com.bitcoinai.backend.simulacion.Cartera;
import com.bitcoinai.backend.simulacion.LibroDeOrdenes;
import java.io.IOException;
import java.nio.file.Path;
import java.time.Duration;

/**
 * Punto de entrada del backend: lee la configuración del entorno, arma la fuente
 * de mercado con caché, la simulación (cartera, libro de órdenes y bot) y
 * arranca el servidor HTTP.
 */
public class Main {

    private static final int SEGUNDOS_ESPERA_AL_APAGAR = 2;

    public static void main(String[] args) throws IOException {
        // Registro en una sola línea: "2026-10-07 18:00:00 INFO GET /health 200 1 ms"
        if (System.getProperty("java.util.logging.SimpleFormatter.format") == null) {
            System.setProperty("java.util.logging.SimpleFormatter.format", "%1$tF %1$tT %4$s %5$s%6$s%n");
        }
        Aplicacion aplicacion = iniciar(Configuracion.desdeEntorno(), "0.0.0.0");
        Runtime.getRuntime().addShutdownHook(new Thread(aplicacion::detener, "apagado-servidor"));
    }

    /**
     * Piezas en marcha del backend, para poder apagarlas juntas.
     *
     * @param servidor   servidor HTTP
     * @param bot        bot simulado
     * @param publicador eventos en tiempo real
     * @param libro      libro de órdenes
     */
    record Aplicacion(Servidor servidor, BotSimulado bot, Publicador publicador, LibroDeOrdenes libro) {

        /** Detiene el bot, cierra las conexiones de tiempo real y luego el servidor. */
        void detener() {
            bot.detener();
            publicador.detener();
            servidor.detener(SEGUNDOS_ESPERA_AL_APAGAR);
        }
    }

    /**
     * Arma y arranca el servidor. Recupera la simulación guardada en DATA_DIR (si
     * hay). El bot queda creado pero detenido; se inicia con POST /api/bot/iniciar.
     *
     * @param config configuración
     * @param host   dirección donde escuchar ("0.0.0.0" en producción)
     * @return las piezas en marcha
     * @throws IOException si no se puede abrir el puerto
     */
    static Aplicacion iniciar(Configuracion config, String host) throws IOException {
        FuenteDeMercado fuente = new CacheMercado(
                new ClienteBinance(config.urlBaseBinance()),
                Duration.ofSeconds(config.ttlCacheSegundos()));
        Publicador publicador = new Publicador(fuente, config.simbolo(), config.maxStreams());

        LibroDeOrdenes libro = new LibroDeOrdenes(new Cartera(), fuente, config.simbolo());
        libro.usarPublicador(publicador);
        AlmacenArchivos almacen = new AlmacenArchivos(Path.of(config.dataDir()));
        boolean recuperado = libro.usarAlmacen(almacen);

        BotSimulado bot = new BotSimulado(libro, fuente, new EstrategiaCombinada(), config.simbolo());
        bot.usarPublicador(publicador);

        Router router = new RutasApi(fuente, config.simbolo()).crearRouter();
        new RutasSimulacion(libro, bot).registrar(router);
        Servidor servidor = new Servidor(host, config.puerto(), router, config.origenPermitido());
        servidor.agregarStream(publicador);
        servidor.iniciar();
        publicador.iniciar();
        System.out.println("Backend iniciado en http://" + host + ":" + servidor.puerto()
                + " (símbolo " + config.simbolo() + ", Binance " + config.urlBaseBinance()
                + "; simulación sin dinero real)");
        System.out.println("Datos de la simulación en " + almacen.getDirectorio().toAbsolutePath().normalize()
                + (recuperado ? " (estado anterior recuperado)" : " (empezando limpio)"));
        return new Aplicacion(servidor, bot, publicador, libro);
    }
}
