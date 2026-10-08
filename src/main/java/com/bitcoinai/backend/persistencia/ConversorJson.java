package com.bitcoinai.backend.persistencia;

import com.bitcoinai.backend.estructuras.Lista;
import com.bitcoinai.backend.simulacion.DatosCartera;
import com.bitcoinai.backend.simulacion.EstadoOrden;
import com.bitcoinai.backend.simulacion.Evento;
import com.bitcoinai.backend.simulacion.Orden;
import com.bitcoinai.backend.simulacion.TipoEvento;
import com.bitcoinai.backend.simulacion.TipoOrden;
import java.util.Map;

/**
 * Convierte el árbol que devuelve {@code JsonLector} (Map, Lista, Double…) en los
 * records de la simulación, validando cada campo. Cualquier dato faltante o del
 * tipo equivocado lanza {@link DatosDanadosException}.
 * Cada conversión es O(tamaño del dato).
 */
final class ConversorJson {

    private ConversorJson() {
    }

    static DatosCartera cartera(Object valor) {
        Map<String, Object> m = mapa(valor, "cartera");
        try {
            return new DatosCartera(numero(m, "saldoInicial"), numero(m, "saldoUsdt"), numero(m, "btc"),
                    numero(m, "costoPosicion"), numero(m, "gananciaRealizada"), numero(m, "comisionesPagadas"));
        } catch (IllegalArgumentException e) {
            throw new DatosDanadosException("cartera con valores imposibles: " + e.getMessage());
        }
    }

    static Orden orden(Object valor) {
        Map<String, Object> m = mapa(valor, "orden");
        long id = entero(m, "id");
        TipoOrden tipo = enumerado(m, "tipo", TipoOrden.class);
        boolean todo = booleano(m, "todo");
        Double monto = numeroOpcional(m, "monto");
        if (id < 1 || (todo && tipo != TipoOrden.VENTA) || (!todo && monto == null)) {
            throw new DatosDanadosException("orden #" + id + " con datos incoherentes");
        }
        return new Orden(id, tipo, monto, todo, enumerado(m, "estado", EstadoOrden.class),
                entero(m, "creadaEn"), enteroOpcional(m, "ejecutadaEn"), numeroOpcional(m, "precioEjecucion"),
                numeroOpcional(m, "cantidadBtc"), numeroOpcional(m, "comision"), texto(m, "motivo"),
                textoOpcional(m, "detalle"));
    }

    static Evento evento(Object valor) {
        Map<String, Object> m = mapa(valor, "evento");
        return new Evento(entero(m, "momento"), enumerado(m, "tipo", TipoEvento.class),
                enteroOpcional(m, "idOrden"), texto(m, "descripcion"));
    }

    // ---------- utilidades ----------

    @SuppressWarnings("unchecked")
    static Map<String, Object> mapa(Object valor, String que) {
        if (!(valor instanceof Map)) {
            throw new DatosDanadosException("se esperaba un objeto en " + que);
        }
        return (Map<String, Object>) valor;
    }

    static Lista<?> lista(Map<String, Object> m, String campo) {
        if (!(m.get(campo) instanceof Lista<?> lista)) {
            throw new DatosDanadosException("falta la lista '" + campo + "'");
        }
        return lista;
    }

    static double numero(Map<String, Object> m, String campo) {
        Double valor = numeroOpcional(m, campo);
        if (valor == null) {
            throw new DatosDanadosException("falta el número '" + campo + "'");
        }
        return valor;
    }

    static Double numeroOpcional(Map<String, Object> m, String campo) {
        Object valor = m.get(campo);
        if (valor == null) {
            return null;
        }
        if (!(valor instanceof Double numero) || !Double.isFinite(numero)) {
            throw new DatosDanadosException("el campo '" + campo + "' debe ser un número");
        }
        return numero;
    }

    static long entero(Map<String, Object> m, String campo) {
        Long valor = enteroOpcional(m, campo);
        if (valor == null) {
            throw new DatosDanadosException("falta el entero '" + campo + "'");
        }
        return valor;
    }

    static Long enteroOpcional(Map<String, Object> m, String campo) {
        Double valor = numeroOpcional(m, campo);
        if (valor == null) {
            return null;
        }
        if (valor != Math.rint(valor)) {
            throw new DatosDanadosException("el campo '" + campo + "' debe ser un entero");
        }
        return valor.longValue();
    }

    static String texto(Map<String, Object> m, String campo) {
        String valor = textoOpcional(m, campo);
        if (valor == null) {
            throw new DatosDanadosException("falta el texto '" + campo + "'");
        }
        return valor;
    }

    static String textoOpcional(Map<String, Object> m, String campo) {
        Object valor = m.get(campo);
        if (valor != null && !(valor instanceof String)) {
            throw new DatosDanadosException("el campo '" + campo + "' debe ser un texto");
        }
        return (String) valor;
    }

    static boolean booleano(Map<String, Object> m, String campo) {
        if (!(m.get(campo) instanceof Boolean valor)) {
            throw new DatosDanadosException("el campo '" + campo + "' debe ser true o false");
        }
        return valor;
    }

    static <E extends Enum<E>> E enumerado(Map<String, Object> m, String campo, Class<E> tipo) {
        String texto = texto(m, campo);
        try {
            return Enum.valueOf(tipo, texto);
        } catch (IllegalArgumentException e) {
            throw new DatosDanadosException("valor desconocido en '" + campo + "': " + texto);
        }
    }
}
