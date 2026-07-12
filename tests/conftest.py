import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contalibre import database, ratelimit
from contalibre.main import app


@pytest.fixture()
def client():
    database.reset_para_pruebas(Path(tempfile.mkdtemp()))
    database.init_control_db()
    ratelimit._intentos.clear()
    with TestClient(app) as c:
        r = c.post(
            "/api/v1/auth/registro",
            json={
                "email": "demo@contalibre.local",
                "password": "password1234",
                "nombre": "Usuaria Demo",
                "empresa_nombre": "Empresa Demo",
            },
        )
        assert r.status_code == 201, r.text
        yield c


@pytest.fixture()
def tercero(client):
    r = client.post(
        "/api/v1/terceros",
        json={"tipo": "ambos", "nif": "B12345678", "nombre": "Acme SL"},
    )
    assert r.status_code == 201, r.text
    return r.json()
