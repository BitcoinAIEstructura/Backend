"""Los correos que envía Nexabit, en texto y en HTML.

El HTML usa tablas y estilos en línea porque Gmail y Outlook ignoran casi todo el CSS.
Los datos de la persona se escapan antes de ponerlos en el HTML.
"""

from html import escape

from bitcoinai.notificaciones.correo import MensajeCorreo

FONDO = "#0b0a0f"
TARJETA = "#16141c"
ORO = "#d9b45a"
TEXTO = "#f3efe6"
SECUNDARIO = "#b9b2a3"


def codigo_verificacion(destino: str, nombre: str, codigo: str, minutos: int) -> MensajeCorreo:
    """El código de 6 dígitos para confirmar el correo al crear la cuenta."""
    asunto = f"{codigo} es tu código para activar Nexabit"
    texto = (
        f"Hola, {nombre}:\n\n"
        f"Tu código para activar tu cuenta de Nexabit es: {codigo}\n\n"
        f"Escríbelo en la página donde creaste la cuenta. Vence en {minutos} minutos.\n\n"
        "Si no creaste una cuenta en Nexabit, ignora este correo: sin el código nadie puede usarla.\n\n"
        "Nexabit es una simulación: nunca te pediremos dinero real ni tu contraseña por correo."
    )
    digitos = "".join(
        f'<td style="padding:0 4px"><div style="width:44px;height:56px;line-height:56px;border-radius:12px;'
        f'background:{FONDO};border:1px solid {ORO};color:{ORO};font-size:28px;font-weight:700;'
        f'font-family:Consolas,monospace;text-align:center">{escape(d)}</div></td>'
        for d in codigo
    )
    html = f"""<!doctype html>
<html lang="es"><body style="margin:0;padding:0;background:{FONDO}">
<div style="display:none;max-height:0;overflow:hidden">Tu código es {escape(codigo)}. Vence en {minutos} minutos.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};padding:32px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="max-width:480px;background:{TARJETA};border-radius:20px;border:1px solid #3a3226;
              font-family:Segoe UI,Helvetica,Arial,sans-serif;color:{TEXTO}">
<tr><td style="padding:28px 28px 8px">
  <p style="margin:0;font-size:22px;font-weight:700;color:{ORO};letter-spacing:.5px">◆ Nexabit</p>
</td></tr>
<tr><td style="padding:8px 28px 0">
  <h1 style="margin:0 0 8px;font-size:22px;color:{TEXTO}">Hola, {escape(nombre)}</h1>
  <p style="margin:0;font-size:15px;line-height:1.6;color:{SECUNDARIO}">
    Este es tu código para activar tu cuenta. Escríbelo en la página donde la creaste.</p>
</td></tr>
<tr><td align="center" style="padding:24px 16px">
  <table role="presentation" cellpadding="0" cellspacing="0"><tr>{digitos}</tr></table>
  <p style="margin:14px 0 0;font-size:13px;color:{SECUNDARIO}">Para copiarlo:
    <span style="font-family:Consolas,monospace;font-size:16px;font-weight:700;color:{TEXTO};
                 letter-spacing:2px">{escape(codigo)}</span></p>
</td></tr>
<tr><td style="padding:0 28px 28px">
  <p style="margin:0 0 12px;font-size:14px;line-height:1.6;color:{SECUNDARIO}">
    Vence en {minutos} minutos. Si no creaste una cuenta en Nexabit, ignora este correo:
    sin el código nadie puede usarla.</p>
  <p style="margin:0;font-size:12px;line-height:1.6;color:#8a8373">
    Nexabit es una simulación: nunca te pediremos dinero real ni tu contraseña por correo.</p>
</td></tr>
</table>
</td></tr></table>
</body></html>"""
    return MensajeCorreo(destino=destino, asunto=asunto, texto=texto, html=html)
