"""Autenticación local: hash de contraseñas y tokens de sesión.

Sin dependencias externas: PBKDF2-HMAC-SHA256 (stdlib hashlib) para
contraseñas, tokens aleatorios (stdlib secrets) para sesiones. Pensado
para uso local/mono-servidor, no para exposición pública en Internet.
"""

import hashlib
import hmac
import secrets

_ITERACIONES = 260_000


def hash_password(password: str) -> str:
    sal = secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(sal), _ITERACIONES)
    return f"{sal}${derivado.hex()}"


def verificar_password(password: str, hash_guardado: str) -> bool:
    try:
        sal, derivado_hex = hash_guardado.split("$", 1)
    except ValueError:
        return False
    derivado = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(sal), _ITERACIONES)
    return hmac.compare_digest(derivado.hex(), derivado_hex)


def generar_token() -> str:
    return secrets.token_urlsafe(32)
