def _activo(client, **extra):
    datos = {
        "nombre": "Equipo informático",
        "fecha_adquisicion": "2023-01-01",
        "valor": 100,
        "valor_residual": 0,
        "vida_util_anios": 3,
        "cuenta_activo": "217",
    }
    datos.update(extra)
    r = client.post("/api/v1/activos", json=datos)
    assert r.status_code == 201, r.text
    return r.json()


def _amortizar(client, activo_id, ejercicio):
    return client.post(f"/api/v1/activos/{activo_id}/amortizar", json={"ejercicio": ejercicio})


def test_plan_lineal_con_ajuste_final(client):
    activo = _activo(client)  # 100 € a 3 años desde 01/01/2023
    a = _amortizar(client, activo["id"], 2023).json()
    assert a["amortizaciones"][0]["importe"] == 33.33
    a = _amortizar(client, activo["id"], 2024).json()
    assert a["amortizaciones"][1]["importe"] == 33.33
    a = _amortizar(client, activo["id"], 2025).json()
    # El último ejercicio absorbe el resto de redondeo
    assert a["amortizaciones"][2]["importe"] == 33.34
    assert a["amortizado"] == 100
    assert a["valor_neto"] == 0

    # Totalmente amortizado: no admite más dotaciones
    assert _amortizar(client, activo["id"], 2026).status_code == 409


def test_prorrateo_primer_ejercicio(client):
    activo = _activo(
        client, fecha_adquisicion="2025-12-02", valor=3650, vida_util_anios=10
    )
    a = _amortizar(client, activo["id"], 2025).json()
    # 30 días de 365 → 365 €/año * 30/365 = 30 €
    assert a["amortizaciones"][0]["importe"] == 30
    a = _amortizar(client, activo["id"], 2026).json()
    assert a["amortizaciones"][1]["importe"] == 365


def test_ejercicio_duplicado_y_anterior(client):
    activo = _activo(client)
    assert _amortizar(client, activo["id"], 2023).status_code == 200
    assert _amortizar(client, activo["id"], 2023).status_code == 409
    assert _amortizar(client, activo["id"], 2022).status_code == 422


def test_dotacion_genera_asiento(client):
    activo = _activo(client)
    a = _amortizar(client, activo["id"], 2023).json()
    asiento_id = a["amortizaciones"][0]["asiento_id"]
    asiento = client.get(f"/api/v1/asientos/{asiento_id}").json()
    assert asiento["fecha"] == "2023-12-31"
    apuntes = {x["cuenta"]: x for x in asiento["apuntes"]}
    assert apuntes["681"]["debe"] == 33.33
    assert apuntes["281"]["haber"] == 33.33

    # Eliminar la dotación elimina también su asiento
    r = client.delete(f"/api/v1/activos/{activo['id']}/amortizaciones/2023")
    assert r.status_code == 204
    assert client.get(f"/api/v1/asientos/{asiento_id}").status_code == 404
