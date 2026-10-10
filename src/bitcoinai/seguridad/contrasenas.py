"""Hash de contraseñas con Argon2id.

Una contraseña nunca se guarda ni se cifra para leerla después: se guarda su
*hash*, un resumen de una sola vía. Para iniciar sesión se calcula el hash de lo
que escribe el usuario y se compara. Ni siquiera quien tenga la base de datos
puede saber la contraseña original.

Argon2id (ganador de la Password Hashing Competition y recomendado por OWASP) es
lento a propósito y usa mucha memoria, así probar millones de contraseñas por
fuerza bruta cuesta demasiado. Cada hash lleva su propia sal aleatoria: dos
usuarios con la misma contraseña tienen hashes distintos.
"""

from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


@dataclass(frozen=True, slots=True)
class ParametrosArgon2:
    """Costo del hash. Los valores por defecto siguen la recomendación de OWASP."""

    iteraciones: int = 3
    memoria_kib: int = 64 * 1024  # 64 MiB
    paralelismo: int = 4


PARAMETROS_RAPIDOS_PARA_PRUEBAS = ParametrosArgon2(iteraciones=1, memoria_kib=8, paralelismo=1)
"""Solo para las pruebas automáticas: seguro de usar en ellas, inseguro en producción."""


class HashContrasenas:
    """Calcula y verifica hashes Argon2id."""

    def __init__(self, parametros: ParametrosArgon2 | None = None) -> None:
        p = parametros or ParametrosArgon2()
        self._hasher = PasswordHasher(time_cost=p.iteraciones, memory_cost=p.memoria_kib, parallelism=p.paralelismo)
        # Hash de una contraseña que nadie tiene: se verifica contra él cuando el correo no
        # existe, así la respuesta tarda lo mismo y no revela qué correos están registrados.
        self._hash_senuelo = self._hasher.hash("contraseña-señuelo-que-nunca-coincide")

    def calcular(self, contrasena: str) -> str:
        """Hash en formato PHC (``$argon2id$v=19$m=…``), con sal aleatoria incluida."""
        return self._hasher.hash(contrasena)

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        """True si la contraseña corresponde al hash. Nunca lanza por una contraseña equivocada."""
        try:
            return self._hasher.verify(hash_guardado, contrasena)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def verificar_senuelo(self, contrasena: str) -> bool:
        """Gasta el mismo tiempo que una verificación real; siempre devuelve False."""
        self.verificar(self._hash_senuelo, contrasena)
        return False

    def necesita_actualizarse(self, hash_guardado: str) -> bool:
        """True si el hash se hizo con parámetros más débiles que los actuales.

        Tras un inicio de sesión correcto se recalcula, así los hashes viejos se
        fortalecen solos cuando se suben los parámetros.
        """
        try:
            return self._hasher.check_needs_rehash(hash_guardado)
        except InvalidHashError:
            return True
