from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.usuarios.actividad import RegistroActividad, TipoActividad
from bitcoinai.usuarios.modelo import DatosRegistro
from bitcoinai.usuarios.repositorio import RepositorioUsuarios


def test_registra_y_lista_del_mas_reciente_al_mas_viejo() -> None:
    bd = BaseDatos(":memory:")
    migrar(bd)
    RepositorioUsuarios(bd, Cifrador(bytes(32))).crear(
        DatosRegistro.validar("Ana", "Pérez", "ana@correo.co", "CC", "1023456789", "3001234567", "Luna-Roja-2026"),
        "h")
    momentos = iter(range(100, 200))
    actividad = RegistroActividad(bd, reloj=lambda: next(momentos))
    actividad.registrar(1, TipoActividad.REGISTRO, "1.1.1.1")
    actividad.registrar(1, TipoActividad.INICIO_FALLIDO, "2.2.2.2", "x" * 500)
    actividad.registrar(1, TipoActividad.INICIO_SESION, "1.1.1.1", "Firefox")
    eventos = tuple(actividad.recientes(1))
    assert tuple(e.tipo for e in eventos) == (TipoActividad.INICIO_SESION, TipoActividad.INICIO_FALLIDO,
                                              TipoActividad.REGISTRO)
    assert eventos[0].detalle == "Firefox" and eventos[0].momento == 102
    assert len(eventos[1].detalle) == 300
    assert actividad.recientes(1, limite=1).tamanio() == 1
    assert actividad.recientes(2).esta_vacia()
