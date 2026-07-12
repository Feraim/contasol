def _asiento(fecha="2026-01-15", debe=100, haber=100):
    return {
        "fecha": fecha,
        "concepto": "Prueba",
        "apuntes": [
            {"cuenta": "572", "debe": debe, "haber": 0},
            {"cuenta": "700", "debe": 0, "haber": haber},
        ],
    }


def test_asiento_valido_y_numeracion(client):
    r1 = client.post("/api/v1/asientos", json=_asiento("2026-01-15"))
    assert r1.status_code == 201, r1.text
    assert r1.json()["numero"] == 1

    r2 = client.post("/api/v1/asientos", json=_asiento("2026-03-02"))
    assert r2.json()["numero"] == 2

    # La numeración se reinicia en cada ejercicio
    r3 = client.post("/api/v1/asientos", json=_asiento("2027-01-05"))
    assert r3.json()["numero"] == 1


def test_asiento_descuadrado_rechazado(client):
    r = client.post("/api/v1/asientos", json=_asiento(debe=100, haber=99.99))
    assert r.status_code == 422
    assert "descuadrado" in r.json()["detail"].lower()


def test_apunte_con_debe_y_haber_rechazado(client):
    r = client.post(
        "/api/v1/asientos",
        json={
            "fecha": "2026-01-15",
            "concepto": "Prueba",
            "apuntes": [
                {"cuenta": "572", "debe": 100, "haber": 50},
                {"cuenta": "700", "debe": 0, "haber": 50},
            ],
        },
    )
    assert r.status_code == 422


def test_cuenta_inexistente_rechazada(client):
    r = client.post(
        "/api/v1/asientos",
        json={
            "fecha": "2026-01-15",
            "concepto": "Prueba",
            "apuntes": [
                {"cuenta": "9999999", "debe": 100, "haber": 0},
                {"cuenta": "700", "debe": 0, "haber": 100},
            ],
        },
    )
    assert r.status_code == 422
    assert "9999999" in r.json()["detail"]


def test_eliminar_asiento(client):
    asiento_id = client.post("/api/v1/asientos", json=_asiento()).json()["id"]
    assert client.delete(f"/api/v1/asientos/{asiento_id}").status_code == 204
    assert client.get(f"/api/v1/asientos/{asiento_id}").status_code == 404
