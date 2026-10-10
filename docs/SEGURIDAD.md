# Seguridad de las cuentas

Cómo se protegen las cuentas y los datos personales, y contra qué ataque sirve cada medida. El dinero de la plataforma es simulado, pero las cuentas y los datos personales son reales, así que se tratan como si manejaran dinero real.

## Dónde está cada cosa

| Pieza | Archivo |
| --- | --- |
| Hash de contraseñas (Argon2id) | `src/bitcoinai/seguridad/contrasenas.py` |
| Política de contraseñas | `src/bitcoinai/seguridad/politica.py` |
| Cifrado AES-256-GCM e índice ciego | `src/bitcoinai/seguridad/cifrado.py` |
| Clave maestra | `src/bitcoinai/seguridad/claves.py` |
| Verificación en dos pasos (TOTP) | `src/bitcoinai/seguridad/totp.py` |
| Códigos de respaldo | `src/bitcoinai/seguridad/respaldo.py` |
| Límite de intentos (Cola) | `src/bitcoinai/seguridad/limitador.py` |
| Reglas de las cuentas | `src/bitcoinai/usuarios/servicio.py` |
| Cookies y endpoints | `src/bitcoinai/api/rutas_cuentas.py` |
| Encabezados de seguridad | `src/bitcoinai/api/middleware.py` |

## Contraseñas

- **Nunca se guardan ni se cifran:** se guarda su **hash Argon2id**, un resumen de una sola vía. Para comprobar un inicio de sesión se calcula el hash de lo escrito y se compara. Ni con la base de datos completa se puede recuperar una contraseña.
- **Argon2id** es el algoritmo recomendado por OWASP. Se usan los parámetros de OWASP: 64 MiB de memoria, 3 iteraciones y 4 hilos. Es lento a propósito: probar millones de contraseñas por fuerza bruta cuesta demasiado.
- **Sal aleatoria por hash:** dos personas con la misma contraseña tienen hashes distintos. Eso inutiliza las tablas precalculadas.
- **Hashes que se fortalecen solos:** si mañana se suben los parámetros, el hash de cada usuario se recalcula la próxima vez que entra.
- **Política:**
  - Mínimo 10 caracteres y al menos 3 tipos de carácter.
  - Ni contraseñas comunes, ni secuencias, ni repeticiones.
  - Nada del nombre, el correo o el documento del propio usuario (comparando sin tildes ni mayúsculas).

## Datos personales cifrados

El correo, el número de documento, el teléfono y el secreto de la verificación en dos pasos se guardan **cifrados con AES-256-GCM**:

- **Ilegibles sin la clave:** quien copie el archivo de la base no puede leer esos datos sin la clave maestra.
- **Detecta alteraciones:** GCM autentica cada valor. Si alguien cambia un byte, el descifrado falla.
- **Nonce aleatorio por valor:** el mismo correo cifrado dos veces da resultados distintos.
- **Contexto autenticado:** cada valor va ligado a su columna ("usuarios.correo"…). Un valor copiado a otra columna no se descifra.
- **Índice ciego (HMAC-SHA256):** para buscar "¿existe este correo?" sin descifrar toda la tabla, se guarda además un HMAC del valor. Es único y determinista, pero no revela el dato sin la clave.
- **Dos claves derivadas:** de la clave maestra se derivan con HKDF una clave para cifrar y otra para los índices.

La clave maestra va en la variable `CLAVE_CIFRADO`, que es secreta. En localhost, si falta, se genera una en `data/clave-cifrado.key`, una carpeta que git ignora.

## Sesiones

- **Token aleatorio de 256 bits en una cookie:**
  - `HttpOnly`: un script inyectado en la página no puede leerla.
  - `SameSite=Strict`: otro sitio no puede hacer peticiones con tu sesión (protege contra CSRF).
  - Con HTTPS, también `Secure` y prefijo `__Host-`.
- **En la base solo está el hash SHA-256 del token:** una copia de la base no sirve para entrar.
- **Expiración:** 12 horas como máximo y 2 horas de inactividad.
- **Control del usuario:** puede ver sus sesiones abiertas (IP, navegador, último uso) y cerrar cualquiera, o todas menos la actual.
- **Cambiar la contraseña cierra las demás sesiones,** por si alguien más la conocía.

## Fuerza bruta y enumeración de cuentas

- **Límite por correo:** 5 contraseñas equivocadas en 15 minutos bloquean ese correo hasta que pase la ventana, **aunque luego llegue la correcta**.
- **Límite por IP:** 20 fallos desde una misma IP, con correos distintos, también bloquean.
- **Otros límites:** 10 registros por hora por IP y 5 códigos de 6 dígitos equivocados cada 15 minutos.
- **Cómo cuenta el limitador:** usa una **Cola** por clave con los momentos de los intentos. Los vencidos salen por el frente, así cada intento cuesta O(1) amortizado y la memoria por clave nunca pasa del máximo.
- **No revela quién tiene cuenta:** el mensaje es siempre "Correo o contraseña incorrectos". Si el correo no existe, se verifica igual contra un hash señuelo, así la respuesta tarda lo mismo. El bloqueo también se aplica a correos inexistentes.
- **IP real:** `X-Forwarded-For` solo se cree con `CONFIAR_PROXY=true`. Si no, cualquiera inventaría una IP para saltarse los límites.

## Verificación en dos pasos (TOTP)

- **Implementación propia de HOTP (RFC 4226) y TOTP (RFC 6238),** probada con los vectores oficiales de los RFC. Funciona con Google Authenticator, Microsoft Authenticator o Authy, sin SMS ni costo.
- **Activación:** el servidor genera un secreto de 160 bits y lo entrega como enlace `otpauth://` para mostrarlo en un código QR. Queda inactivo hasta que el usuario escribe el primer código correcto.
- **Tolerancia:** se acepta el código de 30 s antes o después, por relojes desfasados.
- **Cada código sirve una sola vez:** se guarda el último periodo usado, así un código visto por encima del hombro no sirve.
- **Comparación en tiempo constante:** no da pistas por el tiempo de respuesta.
- **10 códigos de respaldo de un solo uso,** guardados con hash, por si se pierde el teléfono.
- **Desactivar** pide la contraseña y un código.
- **Desafío al iniciar sesión:** con la contraseña correcta se entrega un desafío de 5 minutos en otra cookie `HttpOnly`, con 5 intentos para el código.

## Validación de datos

- **Cédula:**
  - CC: de 5 a 10 dígitos, sin cero inicial.
  - CE: de 5 a 12 letras o números.
- **Teléfono:** se guarda en E.164 (`+573001234567`).
- **Nombres:** solo letras, espacios, apóstrofo o guion. Así no se puede guardar HTML ni scripts.
- **Cuerpos JSON en modo estricto:** se rechazan campos desconocidos (por ejemplo, un `"esAdmin": true` metido a mano) y textos demasiado largos.
- **SQL siempre con parámetros (`?`):** nunca se arma una consulta pegando texto del usuario, lo que evita la inyección de SQL.

## Encabezados HTTP

| Encabezado | Para qué |
| --- | --- |
| `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` | Una respuesta de la API no puede cargar ni ejecutar nada |
| `X-Frame-Options: DENY` | Nadie puede meter la API en un iframe (*clickjacking*) |
| `X-Content-Type-Options: nosniff` | El navegador no "adivina" el tipo de un archivo |
| `Referrer-Policy: no-referrer` | No se filtran URLs a otros sitios |
| `Cache-Control: no-store` (cuentas y sesión) | Los datos personales no quedan en cachés |
| `Strict-Transport-Security` (con HTTPS) | El navegador ya no intenta conectarse por HTTP |

## Registro de actividad

Cada cuenta guarda sus eventos de seguridad, con momento e IP:

- Registro, inicios de sesión e intentos fallidos.
- Códigos de verificación incorrectos y uso de códigos de respaldo.
- Cierres de sesión.
- Cambios de contraseña y de la verificación en dos pasos.

El usuario lo ve en su centro de seguridad, para detectar accesos que no reconoce.

## En producción (Railway)

- **`CLAVE_CIFRADO`:** defínela como variable secreta. Para generar una:

  ```bash
  python -c "from bitcoinai.seguridad.claves import generar_clave_texto as g; print(g())"
  ```

- **`COOKIE_SEGURA=true` y `CONFIAR_PROXY=true`:** Railway sirve por HTTPS detrás de su proxy.
- **`ORIGEN_PERMITIDO`:** la URL exacta del frontend, nunca `*`, porque la cookie necesita credenciales.
- **Copias de seguridad:** guarda la base y la clave por separado. Una sin la otra no sirve para leer los datos, y eso es justamente lo que se busca.
