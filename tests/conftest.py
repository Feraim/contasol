import os
import tempfile

# La BD de pruebas debe fijarse antes de importar el paquete.
os.environ["CONTALIBRE_DB"] = os.path.join(tempfile.mkdtemp(), "contalibre_test.db")

import pytest
from fastapi.testclient import TestClient

from contalibre.database import Base, engine, init_db
from contalibre.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def tercero(client):
    r = client.post(
        "/api/v1/terceros",
        json={"tipo": "ambos", "nif": "B12345678", "nombre": "Acme SL"},
    )
    assert r.status_code == 201, r.text
    return r.json()
