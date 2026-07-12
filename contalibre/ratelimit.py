"""Límite de intentos de login en memoria (proceso único, sin dependencias).

No sustituye a un limitador distribuido si algún día se sirve detrás de
varios workers, pero es suficiente para el caso de uso local/mono-proceso
de esta aplicación.
"""

import time

MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 15 * 60

_intentos: dict[str, list[float]] = {}


def _vigentes(clave: str) -> list[float]:
    ahora = time.monotonic()
    return [t for t in _intentos.get(clave, []) if ahora - t < VENTANA_SEGUNDOS]


def bloqueado(clave: str) -> bool:
    vigentes = _vigentes(clave)
    _intentos[clave] = vigentes
    return len(vigentes) >= MAX_INTENTOS


def registrar_fallo(clave: str) -> None:
    vigentes = _vigentes(clave)
    vigentes.append(time.monotonic())
    _intentos[clave] = vigentes


def limpiar(clave: str) -> None:
    _intentos.pop(clave, None)
