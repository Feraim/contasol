import re
from datetime import datetime, timedelta, timezone

from contalibre import database, models_control, ratelimit


def test_sesion_caduca_en_servidor(client):
    assert client.get("/api/v1/auth/me").status_code == 200
    token = client.cookies.get("contalibre_sesion")

    with database.ControlSession() as db:
        sesion = db.get(models_control.Sesion, token)
        sesion.creada = datetime.now(timezone.utc) - timedelta(days=31)
        db.commit()

    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401

    # La sesión caducada se borra del servidor, no solo se rechaza
    with database.ControlSession() as db:
        assert db.get(models_control.Sesion, token) is None


def test_login_bloquea_tras_varios_fallos(client):
    ratelimit._intentos.clear()
    for _ in range(ratelimit.MAX_INTENTOS):
        r = client.post(
            "/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "mala"}
        )
        assert r.status_code == 401

    r = client.post(
        "/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "password1234"}
    )
    assert r.status_code == 429
    ratelimit._intentos.clear()


def test_login_correcto_limpia_el_contador_de_fallos(client):
    ratelimit._intentos.clear()
    client.post("/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "mala"})
    r = client.post(
        "/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "password1234"}
    )
    assert r.status_code == 200
    assert not ratelimit.bloqueado("demo@contalibre.local")


def test_olvide_password_y_restablecer(client, caplog):
    client.cookies.clear()
    with caplog.at_level("WARNING", logger="contalibre.auth"):
        r = client.post("/api/v1/auth/olvide-password", json={"email": "demo@contalibre.local"})
        assert r.status_code == 202

    token = None
    for registro in caplog.records:
        m = re.search(r"token: (\S+)", registro.message)
        if m:
            token = m.group(1)
    assert token, "el token no se registró en el log"

    r = client.post(
        "/api/v1/auth/restablecer-password",
        json={"token": token, "password_nueva": "nuevaclave123"},
    )
    assert r.status_code == 204

    # La contraseña antigua ya no vale, la nueva sí
    assert client.post(
        "/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "password1234"}
    ).status_code == 401
    r2 = client.post(
        "/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "nuevaclave123"}
    )
    assert r2.status_code == 200

    # El token de un solo uso ya no sirve
    r3 = client.post(
        "/api/v1/auth/restablecer-password",
        json={"token": token, "password_nueva": "otraclave123"},
    )
    assert r3.status_code == 400


def test_olvide_password_no_revela_si_el_email_existe(client):
    r = client.post("/api/v1/auth/olvide-password", json={"email": "no-existe@contalibre.local"})
    assert r.status_code == 202


def test_restablecer_password_invalida_sesiones_existentes(client):
    assert client.get("/api/v1/auth/me").status_code == 200

    import re as _re
    import logging

    logger = logging.getLogger("contalibre.auth")
    tokens = []

    class _Captura(logging.Handler):
        def emit(self, record):
            m = _re.search(r"token: (\S+)", record.getMessage())
            if m:
                tokens.append(m.group(1))

    handler = _Captura()
    logger.addHandler(handler)
    try:
        client.post("/api/v1/auth/olvide-password", json={"email": "demo@contalibre.local"})
    finally:
        logger.removeHandler(handler)
    token = tokens[0]

    client.post(
        "/api/v1/auth/restablecer-password",
        json={"token": token, "password_nueva": "otraclave123"},
    )

    # La cookie de sesión antigua ya no es válida
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_cambiar_password_estando_autenticado(client):
    r = client.put(
        "/api/v1/auth/password",
        json={"password_actual": "password1234", "password_nueva": "otraclave5678"},
    )
    assert r.status_code == 204

    client.cookies.clear()
    assert client.post(
        "/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "password1234"}
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "otraclave5678"}
    ).status_code == 200


def test_cambiar_password_rechaza_password_actual_incorrecta(client):
    r = client.put(
        "/api/v1/auth/password",
        json={"password_actual": "incorrecta", "password_nueva": "otraclave5678"},
    )
    assert r.status_code == 401
