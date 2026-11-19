"""Cuenta de demostración con historial: ``python -m bitcoinai.demo --guardar-en <archivo>``.

Crea (o vuelve a crear) a **Jonathan Mideros** con unos 40 días de recorrido en la
plataforma: órdenes manuales, una etapa con el bot de reglas y otra con el piloto IA,
stop-loss y take-profit, órdenes canceladas y rechazadas, alertas de precio e inicios
de sesión. Las operaciones usan **precios reales** de Binance (velas de 1 hora); si no
hay internet, una serie sintética. Las decisiones son inventadas para la demostración:
no salen de correr la IA en el pasado.

La contraseña se genera al azar y se escribe solo en el archivo de ``--guardar-en``
(nunca en la consola ni en el registro). En un servidor (por ejemplo Railway) se usa
``--contrasena-del-entorno``: la contraseña la elige la persona en la variable
``DEMO_CONTRASENA`` y el script nunca la muestra. ``--correo`` cambia el correo de la cuenta
(por defecto uno del dominio reservado ``.test``). Todo es simulado: no hay dinero real.
"""

import argparse
import math
import os
import random
import secrets
import string
import time
from dataclasses import dataclass
from pathlib import Path

from bitcoinai.__main__ import abrir_base_datos, cargar_env
from bitcoinai.api import Configuracion
from bitcoinai.basedatos import BaseDatos
from bitcoinai.estructuras import Lista, Monticulo
from bitcoinai.mercado import ClienteBinance
from bitcoinai.modelo import Intervalo
from bitcoinai.persistencia import AlmacenBaseDatos
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.seguridad.claves import cargar_clave
from bitcoinai.seguridad.contrasenas import HashContrasenas
from bitcoinai.simulacion import (
    COMISION_POR_DEFECTO,
    SALDO_INICIAL_POR_DEFECTO,
    Cartera,
    EstadoOrden,
    EstadoSimulacion,
    Evento,
    OperacionRechazadaError,
    Orden,
    TipoEvento,
    TipoOrden,
)
from bitcoinai.usuarios.actividad import TipoActividad
from bitcoinai.usuarios.modelo import DatosRegistro
from bitcoinai.usuarios.repositorio import RepositorioUsuarios

NOMBRE, APELLIDO = "Jonathan", "Mideros"
CORREO = "jonathan.mideros@nexabit.test"
"""``.test`` es un dominio reservado: no existe, así que ningún correo sale hacia nadie."""
DOCUMENTO = "1085274196"
TELEFONO = "3157284196"
HORA_MS = 3_600_000
MINUTO_MS = 60_000
VELAS = 1000
SEMILLA = 523

AGENTES = ("Chrome en Windows", "Safari en iPhone", "Chrome en Android", "Edge en Windows")
IPS = ("181.51.32.17", "190.85.144.62", "186.29.71.203")


@dataclass(frozen=True, slots=True)
class VelaSimple:
    tiempo: int
    cierre: float
    maximo: float
    minimo: float


def generar_contrasena() -> str:
    """Una contraseña aleatoria que cumple la política del registro."""
    simbolos = "#$%&*+-=?@"
    while True:
        cuerpo = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        candidata = f"Nx{cuerpo}{secrets.choice(simbolos)}{secrets.randbelow(10)}"
        try:
            DatosRegistro.validar(NOMBRE, APELLIDO, CORREO, "CC", DOCUMENTO, TELEFONO, candidata)
            return candidata
        except ValueError:
            continue


def velas_reales(config: Configuracion) -> tuple[VelaSimple, ...]:
    """Las últimas ~41 días de velas de 1 hora de Binance (o una serie sintética sin internet)."""
    try:
        velas = ClienteBinance(config.url_base_binance).obtener_velas(config.simbolo, Intervalo.H1, VELAS)
        return tuple(VelaSimple(v.tiempo_apertura, v.cierre, v.maximo, v.minimo) for v in velas)
    except Exception as error:  # sin internet la demo igual se puede crear
        print(f"No se pudo leer Binance ({type(error).__name__}); se usa una serie sintética.")
        azar = random.Random(SEMILLA)
        ahora = int(time.time() * 1000) // HORA_MS * HORA_MS
        precio = 98_000.0
        sinteticas: tuple[VelaSimple, ...] = ()
        for i in range(VELAS):
            precio *= math.exp(azar.gauss(0.00005, 0.005))
            sinteticas += (VelaSimple(ahora - (VELAS - i) * HORA_MS, precio, precio * 1.003, precio * 0.997),)
        return sinteticas


class Historia:
    """Va armando las órdenes, los eventos y la cartera en orden cronológico."""

    def __init__(self) -> None:
        self.cartera = Cartera(SALDO_INICIAL_POR_DEFECTO)
        self.registro: Lista[Orden] = Lista()
        self.creadas: Lista[int] = Lista()
        self.eventos: Lista[Evento] = Lista()
        self.siguiente = 1

    def evento(self, momento: int, tipo: TipoEvento, id_orden: int | None, texto: str) -> None:
        self.eventos.agregar(Evento(momento, tipo, id_orden, texto))

    def _crear(self, momento: int, tipo: TipoOrden, monto: float | None, todo: bool, motivo: str) -> Orden:
        orden = Orden(self.siguiente, tipo, monto, todo, EstadoOrden.PENDIENTE, momento, motivo=motivo)
        self.siguiente += 1
        self.creadas.agregar(orden.id)
        que = "vender todo el BTC" if todo else f"{monto:.2f} USDT"
        self.evento(momento, TipoEvento.ORDEN_CREADA, orden.id,
                    f"Orden #{orden.id} de {tipo.name} por {que} creada ({motivo}).")
        return orden

    def operar(self, momento: int, tipo: TipoOrden, monto: float | None, precio: float, motivo: str) -> Orden:
        """Crea y ejecuta (o rechaza) una orden, igual que el libro de órdenes."""
        todo = monto is None
        orden = self._crear(momento, tipo, monto, todo, motivo)
        ejecutada_en = momento + random.randint(2, 40) * 1000
        try:
            if tipo is TipoOrden.COMPRA:
                assert monto is not None
                e = self.cartera.comprar(monto, precio, COMISION_POR_DEFECTO)
            elif todo:
                e = self.cartera.vender_todo(precio, COMISION_POR_DEFECTO)
            else:
                assert monto is not None
                e = self.cartera.vender(monto, precio, COMISION_POR_DEFECTO)
        except OperacionRechazadaError as error:
            final = Orden(orden.id, tipo, monto, todo, EstadoOrden.RECHAZADA, momento, ejecutada_en, precio,
                          motivo=motivo, detalle=str(error))
            self.evento(ejecutada_en, TipoEvento.ORDEN_RECHAZADA, orden.id, f"Orden #{orden.id} rechazada: {error}.")
            self.registro.agregar(final)
            return final
        verbo = "Compró" if tipo is TipoOrden.COMPRA else "Vendió"
        detalle = (f"{verbo} {e.cantidad_btc:.8f} BTC a {precio:.2f} por {e.monto_usdt:.2f} USDT "
                   f"(comisión {e.comision:.2f} USDT).")
        final = Orden(orden.id, tipo, e.monto_usdt if todo else monto, todo, EstadoOrden.EJECUTADA, momento,
                      ejecutada_en, precio, e.cantidad_btc, e.comision, motivo, detalle)
        self.evento(ejecutada_en, TipoEvento.ORDEN_EJECUTADA, orden.id, f"Orden #{orden.id} ejecutada: {detalle}")
        self.registro.agregar(final)
        return final

    def cancelada(self, momento: int, monto: float) -> None:
        orden = self._crear(momento, TipoOrden.COMPRA, monto, False, "manual")
        fin = momento + random.randint(1, 6) * MINUTO_MS
        self.evento(fin, TipoEvento.ORDEN_CANCELADA, orden.id, f"Orden #{orden.id} cancelada.")
        self.registro.agregar(Orden(orden.id, TipoOrden.COMPRA, monto, False, EstadoOrden.CANCELADA, momento,
                                    motivo="manual", detalle="Cancelada por el usuario"))


def _pct(valor: float) -> str:
    return f"{valor * 100:.1f}".replace(".", ",") + " %"


def motivo_reglas(azar: random.Random, senal: str) -> str:
    rsi = azar.randint(28, 46) if senal == "COMPRAR" else azar.randint(55, 74)
    cruce = "alcista" if senal == "COMPRAR" else "bajista"
    peso = azar.uniform(1.4, 2.4)
    return (f"Votación ponderada: {senal} {peso:.2f}, MANTENER {3 - peso:.2f}; cruce {cruce} de medias "
            f"(20/50), RSI {rsi} y MACD {'sobre' if senal == 'COMPRAR' else 'bajo'} su señal.")


def motivo_ia(azar: random.Random, senal: str) -> tuple[str, float]:
    p = azar.uniform(0.56, 0.71) if senal == "COMPRAR" else azar.uniform(0.29, 0.44)
    exactitud = azar.uniform(0.53, 0.58)
    accion = {"COMPRAR": "compra", "VENDER": "vende para proteger lo ganado", "MANTENER": "espera"}[senal]
    texto = (f"El comité da {p * 100:.0f} % de que sube la próxima vela de 1 hora; en velas que no vio acertó "
             f"{exactitud * 100:.0f} % (la base, 51 %). Decisión: {accion}.")
    return texto, abs(p - 0.5) * 2


def construir_historia(velas: tuple[VelaSimple, ...], azar: random.Random) -> Historia:
    """Tres etapas: aprende a mano, prueba el bot de reglas y deja el mando al piloto IA."""
    h = Historia()
    n = len(velas)
    inicio_bot, inicio_ia = n * 30 // 100, n * 58 // 100
    cierres = tuple(v.cierre for v in velas)

    def momento(i: int) -> int:
        return velas[i].tiempo + HORA_MS - azar.randint(1, 50) * MINUTO_MS

    i = 30
    rechazo_hecho = False
    canceladas = 0
    while i < n - 40:
        etapa = "manual" if i < inicio_bot else ("bot" if i < inicio_ia else "ia")
        # Cambios de etapa: encender el bot, pasar al piloto.
        if etapa == "bot" and i - 30 < inicio_bot <= i:
            h.evento(momento(i) - HORA_MS, TipoEvento.BOT_INICIADO, None,
                     "Bot iniciado: estrategia combinada, cada 300 s, velas de 1h, riesgo 20 %, stop-loss 5,0 %, "
                     "take-profit 10,0 %.")
        if etapa == "ia" and i - 40 < inicio_ia <= i:
            h.evento(momento(i) - 2 * HORA_MS, TipoEvento.BOT_DETENIDO, None, "Bot detenido.")
            h.evento(momento(i) - HORA_MS, TipoEvento.BOT_INICIADO, None,
                     "Piloto IA encendido: el comité de la IA decide cada 300 s con velas de 1h; topes: riesgo "
                     "25 %, stop-loss 5,0 %, take-profit 10,0 %.")
        if etapa == "manual" and not rechazo_hecho and h.cartera.btc == 0 and i > 60:
            h.operar(momento(i), TipoOrden.VENTA, 250.0, cierres[i], "manual")  # aún no tenía BTC
            rechazo_hecho = True
        if etapa == "manual" and canceladas < 2 and i > 90 * (canceladas + 1):  # se arrepintió dos veces
            h.cancelada(momento(i) - 20 * MINUTO_MS, float(azar.choice((200, 500, 750))))
            canceladas += 1

        ventana = azar.randint(12, 60)
        tramo = cierres[i + 1:i + 1 + ventana]
        prob_ganar = {"manual": 0.58, "bot": 0.62, "ia": 0.71}[etapa]
        if max(tramo) < cierres[i] * 1.012:  # sin una oportunidad clara no opera (ni gana ni pierde)
            i += azar.randint(3, 12)
            continue
        gana = azar.random() < prob_ganar
        if gana:
            j = i + 1 + tramo.index(max(tramo))
        else:  # las pérdidas se cortan con un stop-loss (entre 1,2 % y 2,5 %), como haría el bot
            limite = cierres[i] * (1 - azar.uniform(0.012, 0.025))
            j = next((i + 1 + d for d, c in enumerate(tramo) if c <= limite), i + 1 + tramo.index(min(tramo)))

        precio_compra, precio_venta = cierres[i], cierres[j]
        variacion = precio_venta / precio_compra - 1
        if etapa == "manual":
            monto = float(azar.choice((300, 500, 800, 1000, 1200, 1500, 2000)))
            motivo_c = motivo_v = "manual"
        elif etapa == "bot":
            monto = round(h.cartera.saldo_usdt * 0.20, 2)
            senal_c = motivo_reglas(azar, "COMPRAR")
            h.evento(momento(i) - 30_000, TipoEvento.DECISION_BOT, None,
                     f"El bot decidió COMPRAR (confianza {azar.uniform(0.45, 0.8):.2f}): {senal_c}")
            motivo_c = f"señal del bot: {senal_c}"
            if variacion >= 0.04:
                motivo_v = f"take-profit: el precio {precio_venta:.2f} está {variacion * 100:+.2f} % respecto del costo"
            elif variacion <= -0.03:
                motivo_v = f"stop-loss: el precio {precio_venta:.2f} está {variacion * 100:+.2f} % respecto del costo"
            else:
                motivo_v = f"señal del bot: {motivo_reglas(azar, 'VENDER')}"
        else:
            texto_c, conf = motivo_ia(azar, "COMPRAR")
            riesgo = min(0.25, max(0.06, 0.25 * conf * 2.5))
            monto = round(h.cartera.saldo_usdt * riesgo, 2)
            h.evento(momento(i) - 30_000, TipoEvento.DECISION_BOT, None,
                     f"La IA decidió COMPRAR (confianza {conf:.2f}): {texto_c}")
            motivo_c = f"piloto IA: {texto_c}"
            stop = azar.uniform(0.012, 0.022)
            if variacion >= 2 * stop:
                motivo_v = (f"piloto IA · take-profit: el precio {precio_venta:.2f} está {variacion * 100:+.2f} % "
                            f"respecto del costo (objetivo {_pct(2 * stop)})")
            elif variacion <= -stop:
                motivo_v = (f"piloto IA · stop-loss: el precio {precio_venta:.2f} está {variacion * 100:+.2f} % "
                            f"respecto del costo (límite {_pct(stop)})")
            else:
                texto_v, conf_v = motivo_ia(azar, "VENDER")
                h.evento(momento(j) - 30_000, TipoEvento.DECISION_BOT, None,
                         f"La IA decidió VENDER (confianza {conf_v:.2f}): {texto_v}")
                motivo_v = f"piloto IA: {texto_v}"

        h.operar(momento(i), TipoOrden.COMPRA, monto, precio_compra, motivo_c)
        venta = h.operar(momento(j), TipoOrden.VENTA, None, precio_venta, motivo_v)
        if "stop-loss" in motivo_v:
            h.evento(venta.ejecutada_en or momento(j), TipoEvento.STOP_LOSS, venta.id,
                     f"{'La IA' if etapa == 'ia' else 'El bot'} vende todo por {motivo_v.split('· ')[-1]}.")
        elif "take-profit" in motivo_v:
            h.evento(venta.ejecutada_en or momento(j), TipoEvento.TAKE_PROFIT, venta.id,
                     f"{'La IA' if etapa == 'ia' else 'El bot'} vende todo por {motivo_v.split('· ')[-1]}.")
        if etapa != "manual":  # entre operaciones, el bot revisa y decide esperar
            for k in range(j + 4, min(j + 30, n - 41), 6):
                if etapa == "ia":
                    h.evento(momento(k), TipoEvento.DECISION_BOT, None,
                             f"La IA decidió MANTENER (confianza {azar.uniform(0.02, 0.1):.2f}): El comité da "
                             f"{azar.randint(47, 54)} % de que sube la próxima vela de 1 hora: no hay ventaja clara. "
                             "Decisión: espera.")
                else:
                    h.evento(momento(k), TipoEvento.DECISION_BOT, None,
                             "El bot decidió MANTENER (confianza 0.00): Votación ponderada: COMPRAR 0.00, "
                             "VENDER 0.00, MANTENER 3.00; sin cruces ni extremos de RSI.")
        i = j + azar.randint(4, 30)

    # Hace unas horas el piloto compró y la posición sigue abierta; luego Jonathan lo apagó.
    k = n - 9
    texto, conf = motivo_ia(azar, "COMPRAR")
    h.evento(momento(k) - 30_000, TipoEvento.DECISION_BOT, None,
             f"La IA decidió COMPRAR (confianza {conf:.2f}): {texto}")
    h.operar(momento(k), TipoOrden.COMPRA, round(h.cartera.saldo_usdt * 0.18, 2), cierres[k], f"piloto IA: {texto}")
    h.evento(momento(n - 3), TipoEvento.BOT_DETENIDO, None, "Bot detenido.")
    return h


def _ordenar(eventos: Lista[Evento]) -> Lista[Evento]:
    """Eventos del más viejo al más nuevo, con un montículo (heapsort). Complejidad: O(n log n)."""
    monticulo: Monticulo[Evento] = Monticulo(lambda e: e.momento)
    for e in eventos:
        monticulo.insertar(e)
    ordenados: Lista[Evento] = Lista()
    while not monticulo.esta_vacia():
        ordenados.agregar(monticulo.extraer())
    return ordenados


def crear_demo(bd: BaseDatos, cifrador: Cifrador, velas: tuple[VelaSimple, ...], contrasena: str,
               correo: str = CORREO) -> int:
    """Borra la cuenta de demostración si existía y la crea de nuevo con su historial. Devuelve su id."""
    azar = random.Random(SEMILLA)
    random.seed(SEMILLA)
    primera = velas[0].tiempo
    creado = primera - 26 * HORA_MS
    repo = RepositorioUsuarios(bd, cifrador, reloj=lambda: creado)
    existente = repo.credenciales_por_correo(correo)
    if existente is not None:
        bd.ejecutar("DELETE FROM usuarios WHERE id = ?", (existente.usuario_id,))
    datos = DatosRegistro.validar(NOMBRE, APELLIDO, correo, "CC", DOCUMENTO, TELEFONO, contrasena)
    usuario = repo.crear(datos, HashContrasenas().calcular(contrasena), correo_verificado=True)
    uid = usuario.id

    historia = construir_historia(velas, azar)
    ahora = int(time.time() * 1000)
    AlmacenBaseDatos(bd, uid, reloj=lambda: ahora).guardar(EstadoSimulacion(
        historia.cartera.datos(), historia.siguiente, Lista(), historia.registro, historia.creadas,
        _ordenar(historia.eventos)))

    # Actividad de la cuenta: registro, correo confirmado, inicios y cierres de sesión, cambio de contraseña.
    filas: Lista[tuple[object, ...]] = Lista()
    filas.agregar((uid, creado, TipoActividad.REGISTRO.name, IPS[0], ""))
    filas.agregar((uid, creado + 2 * MINUTO_MS, TipoActividad.CORREO_VERIFICADO.name, IPS[0], ""))
    momento = creado + 3 * MINUTO_MS
    while momento < ahora - 3 * HORA_MS:
        agente, ip = azar.choice(AGENTES), azar.choice(IPS)
        filas.agregar((uid, momento, TipoActividad.INICIO_SESION.name, ip, agente))
        if azar.random() < 0.5:
            filas.agregar((uid, momento + azar.randint(10, 90) * MINUTO_MS, TipoActividad.CIERRE_SESION.name, ip, ""))
        momento += azar.randint(18, 60) * HORA_MS
    filas.agregar((uid, creado + 9 * 24 * HORA_MS, TipoActividad.INICIO_FALLIDO.name, IPS[2], ""))
    filas.agregar((uid, creado + 16 * 24 * HORA_MS, TipoActividad.CONTRASENA_CAMBIADA.name, IPS[0], ""))
    filas.agregar((uid, ahora - 2 * HORA_MS, TipoActividad.INICIO_SESION.name, IPS[0], AGENTES[0]))
    bd.ejecutar_muchos("INSERT INTO actividad (usuario_id, momento, tipo, ip, detalle) VALUES (?, ?, ?, ?, ?)",
                       (f for f in filas))

    # Alertas: una que ya se cumplió y dos activas alrededor del precio de ahora.
    precio = velas[-1].cierre
    medio = velas[len(velas) // 2]
    bd.ejecutar("INSERT INTO alertas (usuario_id, tipo, precio, estado, creada_en, disparada_en, precio_disparo)"
                " VALUES (?, 'SUBE_A', ?, 'DISPARADA', ?, ?, ?)",
                (uid, round(medio.cierre * 0.99, -2), medio.tiempo - 30 * HORA_MS, medio.tiempo, medio.cierre))
    bd.ejecutar("INSERT INTO alertas (usuario_id, tipo, precio, estado, creada_en)"
                " VALUES (?, 'SUBE_A', ?, 'ACTIVA', ?)",
                (uid, round(precio * 1.06, -2), ahora - 20 * HORA_MS))
    bd.ejecutar("INSERT INTO alertas (usuario_id, tipo, precio, estado, creada_en)"
                " VALUES (?, 'BAJA_A', ?, 'ACTIVA', ?)",
                (uid, round(precio * 0.93, -2), ahora - 20 * HORA_MS))
    return uid


def guardar_credenciales(ruta: Path, contrasena: str, correo: str = CORREO) -> None:
    ruta.write_text(
        "# Cuenta de demostración de Nexabit (solo local)\n\n"
        "Creada con `python -m bitcoinai.demo` en la carpeta `Backend`. Este archivo no está en ningún\n"
        "repositorio: no lo subas a GitHub.\n\n"
        f"- Nombre: {NOMBRE} {APELLIDO}\n"
        f"- Correo: `{correo}`"
        + (" (dominio reservado .test: no recibe correos de verdad)" if correo == CORREO else "") + "\n"
        f"- Contraseña: `{contrasena}`\n\n"
        "Entra en http://localhost:3000/iniciar-sesion. La cuenta ya tiene el correo confirmado y no usa\n"
        "verificación en dos pasos. Si vuelves a correr el script, la cuenta se recrea con otra contraseña.\n\n"
        "## Cómo abrir Nexabit\n\n"
        "1. Backend, en `Backend`: `.venv/Scripts/python.exe -m bitcoinai` (puerto 8080).\n"
        "2. Frontend, en `Frontend-Plataforma`: `npm run dev` (puerto 3000).\n"
        "3. Abre http://localhost:3000.\n",
        encoding="utf-8")


VARIABLE_CONTRASENA = "DEMO_CONTRASENA"


def contrasena_del_entorno(correo: str) -> str:
    """La contraseña de ``DEMO_CONTRASENA``, revisada con la política del registro.

    Raises:
        SystemExit: si falta o no cumple la política (el mensaje nunca incluye la contraseña).
    """
    contrasena = os.environ.get(VARIABLE_CONTRASENA, "")
    if not contrasena:
        raise SystemExit(f"Falta la variable {VARIABLE_CONTRASENA} con la contraseña de la cuenta.")
    try:
        DatosRegistro.validar(NOMBRE, APELLIDO, correo, "CC", DOCUMENTO, TELEFONO, contrasena)
    except ValueError as error:
        raise SystemExit(f"{VARIABLE_CONTRASENA} no sirve: {error}") from None
    return contrasena


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea la cuenta de demostración de Jonathan Mideros.")
    destino = parser.add_mutually_exclusive_group(required=True)
    destino.add_argument("--guardar-en", type=Path,
                         help="genera una contraseña y la escribe en este archivo (fuera de git)")
    destino.add_argument("--contrasena-del-entorno", action="store_true",
                         help=f"usa la contraseña de la variable {VARIABLE_CONTRASENA} (no la muestra)")
    parser.add_argument("--correo", default=CORREO, help=f"correo de la cuenta (por defecto {CORREO})")
    args = parser.parse_args()
    cargar_env()
    correo = args.correo.strip().lower()
    contrasena = contrasena_del_entorno(correo) if args.contrasena_del_entorno else generar_contrasena()
    config = Configuracion.desde_entorno()
    bd = abrir_base_datos(config)
    velas = velas_reales(config)
    uid = crear_demo(bd, Cifrador(cargar_clave(config.data_dir)), velas, contrasena, correo)
    if args.guardar_en is not None:
        guardar_credenciales(args.guardar_en, contrasena, correo)
        print(f"Cuenta de demostración lista (usuario #{uid}, {correo}). Contraseña guardada en {args.guardar_en}.")
    else:
        print(f"Cuenta de demostración lista (usuario #{uid}, {correo}), con la contraseña de "
              f"{VARIABLE_CONTRASENA}. Ya puedes borrar esa variable.")


if __name__ == "__main__":
    main()
