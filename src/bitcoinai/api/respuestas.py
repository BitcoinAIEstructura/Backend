"""Respuestas JSON con el formato del contrato."""

from fastapi.responses import JSONResponse


class RespuestaJson(JSONResponse):
    """JSON compacto en UTF-8, con ``Content-Type: application/json; charset=utf-8``.

    Es la respuesta por defecto de toda la API, incluidos los errores.
    """

    media_type = "application/json; charset=utf-8"


def respuesta_error(codigo: int, mensaje: str, encabezados: dict[str, str] | None = None) -> RespuestaJson:
    """Error con la forma del contrato: ``{"error": "mensaje"}``."""
    return RespuestaJson({"error": mensaje}, status_code=codigo, headers=encabezados)
