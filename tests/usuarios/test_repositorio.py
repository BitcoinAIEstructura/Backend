import pytest

from bitcoinai.basedatos import BaseDatos
from bitcoinai.basedatos.migraciones import migrar
from bitcoinai.estructuras import Lista
from bitcoinai.seguridad.cifrado import Cifrador
from bitcoinai.usuarios.modelo import DatosRegistro
from bitcoinai.usuarios.repositorio import RepositorioUsuarios, UsuarioDuplicadoError
from bitcoinai.usuarios.validacion import TipoDocumento


def datos(correo: str = "ana@correo.co", documento: str = "1023456789") -> DatosRegistro:
    return DatosRegistro.validar("Ana", "Pérez", correo, "CC", documento, "3001234567", "Luna-Roja-2026")


@pytest.fixture
def bd() -> BaseDatos:
    base = BaseDatos(":memory:")
    migrar(base)
    return base


@pytest.fixture
def repo(bd: BaseDatos) -> RepositorioUsuarios:
    return RepositorioUsuarios(bd, Cifrador(bytes(32)), reloj=lambda: 1_000)


def test_crear_y_leer(repo: RepositorioUsuarios) -> None:
    usuario = repo.crear(datos(), "$argon2id$hash")
    assert (usuario.id, usuario.correo, usuario.numero_documento, usuario.telefono) == (
        1, "ana@correo.co", "1023456789", "+573001234567")
    assert usuario.creado_en == 1_000 and not usuario.verificacion_dos_pasos
    assert repo.por_id(1) == usuario
    assert repo.por_id(2) is None
    credenciales = repo.credenciales_por_correo("ana@correo.co")
    assert credenciales is not None and credenciales.contrasena_hash == "$argon2id$hash"
    assert repo.credenciales_por_correo("otro@correo.co") is None
    assert repo.existe_documento(TipoDocumento.CC, "1023456789")
    assert not repo.existe_documento(TipoDocumento.CE, "1023456789")


def test_los_datos_personales_no_quedan_en_claro(repo: RepositorioUsuarios, bd: BaseDatos) -> None:
    repo.crear(datos(), "h")
    fila = bd.una("SELECT * FROM usuarios")
    assert fila is not None
    crudo = b"".join(v if isinstance(v, bytes) else str(v).encode() for v in tuple(fila))
    for secreto in (b"ana@correo.co", b"1023456789", b"3001234567"):
        assert secreto not in crudo


def test_correo_o_documento_duplicado(repo: RepositorioUsuarios) -> None:
    repo.crear(datos(), "h")
    with pytest.raises(UsuarioDuplicadoError):
        repo.crear(datos(documento="999999"), "h")
    with pytest.raises(UsuarioDuplicadoError):
        repo.crear(datos(correo="otra@correo.co"), "h")


def test_contrasena_y_totp(repo: RepositorioUsuarios) -> None:
    repo.crear(datos(), "viejo")
    repo.cambiar_contrasena(1, "nuevo")
    repo.guardar_totp(1, "JBSWY3DPEHPK3PXP", activo=True)
    c = repo.credenciales(1)
    assert c is not None and (c.contrasena_hash, c.totp_secreto, c.totp_activo) == ("nuevo", "JBSWY3DPEHPK3PXP", True)
    assert repo.marcar_paso_totp(1, 10)
    assert not repo.marcar_paso_totp(1, 10)  # el mismo paso no vale dos veces
    assert repo.marcar_paso_totp(1, 11)
    repo.guardar_totp(1, None, activo=False)
    c = repo.credenciales(1)
    assert c is not None and c.totp_secreto is None and c.totp_ultimo_paso is None


def test_codigos_de_respaldo_de_un_solo_uso(repo: RepositorioUsuarios) -> None:
    repo.crear(datos(), "h")
    hashes: Lista[bytes] = Lista()
    for i in range(3):
        hashes.agregar(bytes([i]) * 32)
    repo.reemplazar_codigos(1, hashes)
    assert repo.codigos_restantes(1) == 3
    assert repo.usar_codigo(1, bytes([1]) * 32)
    assert not repo.usar_codigo(1, bytes([1]) * 32)
    assert not repo.usar_codigo(1, bytes([9]) * 32)
    assert repo.codigos_restantes(1) == 2
