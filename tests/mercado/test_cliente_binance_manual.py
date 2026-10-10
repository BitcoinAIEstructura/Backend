"""Prueba manual contra la API real de Binance: necesita internet.

No corre con ``pytest`` normal (está marcada como "manual"). Para correrla a mano:

    pytest -m manual -s

Si Binance está bloqueado en tu país, define antes BINANCE_BASE_URL
(por ejemplo https://data-api.binance.vision).
"""

from datetime import UTC, datetime

import pytest

from bitcoinai.mercado import ClienteBinance
from bitcoinai.modelo import Intervalo


@pytest.mark.manual
def test_descarga_diez_velas_diarias_reales_de_btcusdt() -> None:
    with ClienteBinance() as cliente:
        velas = cliente.obtener_velas("BTCUSDT", Intervalo.D1, 10)
        precio = cliente.obtener_precio_actual("BTCUSDT")

    print(f"\nURL base: {cliente.url_base}")
    print(f"{'Fecha (UTC)':<12}  {'Apertura':>12}  {'Máximo':>12}  {'Mínimo':>12}  {'Cierre':>12}  {'Volumen':>10}")
    for v in velas:
        fecha = datetime.fromtimestamp(v.tiempo_apertura / 1000, tz=UTC).date()
        print(f"{fecha!s:<12}  {v.apertura:>12.2f}  {v.maximo:>12.2f}  {v.minimo:>12.2f}  "
              f"{v.cierre:>12.2f}  {v.volumen:>10.2f}")
    print(f"Precio actual BTCUSDT: {precio:.2f}")

    assert velas.tamanio() == 10
    assert precio > 0
