"""Errores del paquete de mercado."""


class MercadoError(Exception):
    """Error al obtener o validar datos de mercado.

    La fuente no responde, responde con un código de error o entrega datos inválidos.
    """
