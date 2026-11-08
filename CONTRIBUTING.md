# Guía de contribución

## Requisitos

- Python 3.13 o superior.
- `pip` actualizado.

## Puesta en marcha

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Ajusta `.env` solo con valores locales. Ese archivo está ignorado por Git y nunca debe subirse.

## Flujo de trabajo

1. Crea una rama descriptiva: `feat/mi-cambio`, `fix/mi-arreglo` o `docs/mi-guia`.
2. Haz cambios pequeños y enfocados en un solo objetivo.
3. Antes de abrir un pull request, ejecuta las mismas revisiones del CI:

```bash
ruff check
mypy src
pytest
```

Para probar también las rutas que necesitan internet (Binance real):

```bash
pytest -m manual
```

## Estilo de código

- Respeta el límite de 120 caracteres configurado en `pyproject.toml`.
- Usa tipos explícitos; el proyecto se revisa con `mypy` en modo estricto.
- Ordena los imports con Ruff (`I`) y mantén los nombres en `snake_case` (`N`).
- Escribe docstrings en español, en imperativo y explicando el porqué.
- No uses `list`, `dict` ni `heapq` como estructuras del dominio: el proyecto implementa las suyas en `src/bitcoinai/estructuras`.
- No subas secretos, bases de datos ni archivos `.env` reales.
- Añade una prueba cuando cambies comportamiento; las pruebas viven en `tests/`.

## Commits

Usa mensajes claros con prefijo convencional:

- `feat:` nueva funcionalidad.
- `fix:` corrección de errores.
- `docs:` documentación.
- `style:` formato sin cambios de lógica.
- `chore:` mantenimiento, configuración o dependencias.
- `test:` pruebas.

Ejemplo: `docs: documentar el punto de entrada del backend`.
