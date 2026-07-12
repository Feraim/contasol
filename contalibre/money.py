"""Conversión entre euros (Decimal) y céntimos (int).

Todo el dinero se almacena y opera en céntimos enteros para que los
cuadres de partida doble sean exactos.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def a_centimos(euros) -> int:
    """Convierte un importe en euros (Decimal/str/float/int) a céntimos."""
    d = euros if isinstance(euros, Decimal) else Decimal(str(euros))
    return int(d.quantize(CENT, rounding=ROUND_HALF_UP) * 100)


def a_euros(centimos: int) -> float:
    """Convierte céntimos a euros para la salida JSON de la API."""
    return float(Decimal(centimos) / 100)
