# Backend del bot de Bitcoin (Python + FastAPI): imagen en dos etapas.
# El servidor lee el puerto de la variable PORT (Railway la inyecta; sin ella usa 8080).

# ---------- Etapa 1: construcción ----------
FROM python:3.13-slim AS construccion
WORKDIR /build

# Un entorno virtual aparte, para copiarlo entero a la imagen final.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Primero solo pyproject.toml (y el README que declara): mientras no cambien, Docker
# reutiliza esta capa con las dependencias (FastAPI, uvicorn, httpx) ya instaladas.
COPY pyproject.toml README.md ./
RUN mkdir -p src/bitcoinai && touch src/bitcoinai/__init__.py \
    && pip install . && pip uninstall -y bitcoinai-backend

# Después el código, y se instala el proyecto (las pruebas corren en el CI).
COPY src ./src
RUN pip install --no-deps .

# ---------- Etapa 2: ejecución ----------
FROM python:3.13-slim
WORKDIR /app

# Usuario sin privilegios. La carpeta ./data (DATA_DIR por defecto) le pertenece.
RUN groupadd --system backend && useradd --system --gid backend --home-dir /app --no-create-home backend \
    && mkdir -p /app/data && chown -R backend:backend /app

# Solo el entorno virtual de la etapa anterior; pip y el código fuente no llegan a esta imagen.
COPY --from=construccion /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER backend
EXPOSE 8080

# Forma exec: Python es el proceso 1 y recibe las señales de apagado (SIGTERM) directamente.
CMD ["python", "-m", "bitcoinai"]
