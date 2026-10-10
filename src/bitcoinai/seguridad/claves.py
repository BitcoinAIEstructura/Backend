"""De dónde sale la clave maestra de cifrado.

En producción va en la variable de entorno ``CLAVE_CIFRADO`` (32 bytes en
base64), configurada como secreto en la plataforma. En localhost, si no está
definida, se genera una al azar la primera vez y se guarda en un archivo dentro de
``DATA_DIR`` (que git ignora), así los datos siguen legibles tras reiniciar.

Si la clave se pierde, los datos cifrados no se pueden recuperar: es el precio
de que nadie más pueda leerlos.
"""

import base64
import binascii
import logging
import os
import secrets
from collections.abc import Mapping
from pathlib import Path

from bitcoinai.seguridad.cifrado import LONGITUD_CLAVE

ARCHIVO_CLAVE = "clave-cifrado.key"

LOG = logging.getLogger("bitcoinai.seguridad")


def decodificar_clave(texto: str) -> bytes:
    """Base64 (normal o URL) → 32 bytes.

    Raises:
        ValueError: con un mensaje claro si no es base64 o no mide 32 bytes.
    """
    limpio = texto.strip()
    try:
        clave = base64.urlsafe_b64decode(limpio.replace("+", "-").replace("/", "_") + "=" * (-len(limpio) % 4))
    except (binascii.Error, ValueError) as error:
        raise ValueError("CLAVE_CIFRADO debe estar en base64") from error
    if len(clave) != LONGITUD_CLAVE:
        raise ValueError(f"CLAVE_CIFRADO debe tener {LONGITUD_CLAVE} bytes (en base64, 44 caracteres)")
    return clave


def generar_clave_texto() -> str:
    """Una clave nueva al azar, en base64 URL, lista para ``CLAVE_CIFRADO``."""
    return base64.urlsafe_b64encode(secrets.token_bytes(LONGITUD_CLAVE)).decode("ascii")


def cargar_clave(directorio_datos: str | Path, entorno: Mapping[str, str] | None = None) -> bytes:
    """La clave de ``CLAVE_CIFRADO`` o, si no hay, la del archivo local (creándolo si falta)."""
    variables = os.environ if entorno is None else entorno
    texto = variables.get("CLAVE_CIFRADO", "").strip()
    if texto:
        return decodificar_clave(texto)
    archivo = Path(directorio_datos) / ARCHIVO_CLAVE
    if archivo.exists():
        return decodificar_clave(archivo.read_text(encoding="ascii"))
    archivo.parent.mkdir(parents=True, exist_ok=True)
    # "x": falla si otro proceso lo creó justo ahora, en vez de pisar su clave.
    with open(archivo, "x", encoding="ascii") as salida:
        salida.write(generar_clave_texto())
    try:
        os.chmod(archivo, 0o600)  # solo el dueño puede leerla (en Windows no tiene efecto)
    except OSError:
        pass
    LOG.warning("No hay CLAVE_CIFRADO: se generó una clave local en %s. En producción define CLAVE_CIFRADO.", archivo)
    return decodificar_clave(archivo.read_text(encoding="ascii"))
