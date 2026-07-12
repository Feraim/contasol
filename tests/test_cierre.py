def _asiento(client, fecha, concepto, apuntes):
    r = client.post(
        "/api/v1/asientos", json={"fecha": fecha, "concepto": concepto, "apuntes": apuntes}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _cerrar(client, anio):
    return client.post(f"/api/v1/ejercicios/{anio}/cerrar")


def _abrir(client, anio):
    return client.post(f"/api/v1/ejercicios/{anio}/abrir")


def _saldo(client, cuenta):
    return client.get("/api/v1/informes/mayor", params={"cuenta": cuenta}).json()["saldo"]


def test_regularizacion_y_cierre_saldan_las_cuentas(client):
    _asiento(
        client, "2023-01-01", "Aportación capital",
        [{"cuenta": "572", "debe": 3000}, {"cuenta": "100", "haber": 3000}],
    )
    _asiento(
        client, "2023-06-01", "Venta",
        [{"cuenta": "570", "debe": 1000}, {"cuenta": "700", "haber": 1000}],
    )
    _asiento(
        client, "2023-07-01", "Alquiler",
        [{"cuenta": "621", "debe": 400}, {"cuenta": "570", "haber": 400}],
    )

    r = _cerrar(client, 2023)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["cerrado"] is True
    assert datos["resultado"] == 600

    reg = client.get(f"/api/v1/asientos/{datos['asiento_regularizacion_id']}").json()
    apuntes_reg = {a["cuenta"]: a for a in reg["apuntes"]}
    assert apuntes_reg["700"]["debe"] == 1000
    assert apuntes_reg["621"]["haber"] == 400
    assert apuntes_reg["129"]["haber"] == 600

    cierre = client.get(f"/api/v1/asientos/{datos['asiento_cierre_id']}").json()
    assert cierre["fecha"] == "2023-12-31"
    cuentas_cierre = {a["cuenta"] for a in cierre["apuntes"]}
    assert cuentas_cierre == {"572", "100", "570", "129"}

    for cuenta in ("572", "570", "700", "621", "100", "129"):
        assert _saldo(client, cuenta) == 0, cuenta


def test_no_se_puede_cerrar_dos_veces(client):
    _asiento(
        client, "2023-01-01", "Aportación",
        [{"cuenta": "572", "debe": 100}, {"cuenta": "100", "haber": 100}],
    )
    assert _cerrar(client, 2023).status_code == 200
    assert _cerrar(client, 2023).status_code == 409


def test_bloqueo_de_asientos_en_ejercicio_cerrado(client):
    aportacion = _asiento(
        client, "2023-01-01", "Aportación",
        [{"cuenta": "572", "debe": 100}, {"cuenta": "100", "haber": 100}],
    )
    assert _cerrar(client, 2023).status_code == 200

    r = client.post(
        "/api/v1/asientos",
        json={
            "fecha": "2023-12-15",
            "concepto": "tarde",
            "apuntes": [{"cuenta": "570", "debe": 10}, {"cuenta": "700", "haber": 10}],
        },
    )
    assert r.status_code == 409

    assert client.delete(f"/api/v1/asientos/{aportacion['id']}").status_code == 409


def test_cierre_y_apertura_secuenciales(client):
    _asiento(
        client, "2023-01-01", "Aportación",
        [{"cuenta": "572", "debe": 1000}, {"cuenta": "100", "haber": 1000}],
    )
    _asiento(
        client, "2024-01-10", "Venta 2024",
        [{"cuenta": "570", "debe": 200}, {"cuenta": "700", "haber": 200}],
    )

    assert _cerrar(client, 2024).status_code == 409
    assert _abrir(client, 2024).status_code == 409

    assert _cerrar(client, 2023).status_code == 200
    assert _cerrar(client, 2024).status_code == 409  # falta abrir 2024 primero
    assert _abrir(client, 2024).status_code == 200
    assert _cerrar(client, 2024).status_code == 200

    assert _cerrar(client, 2023).status_code == 409
    assert _abrir(client, 2024).status_code == 409


def test_apertura_reabre_los_mismos_saldos(client):
    _asiento(
        client, "2023-01-01", "Aportación",
        [{"cuenta": "572", "debe": 1000}, {"cuenta": "100", "haber": 1000}],
    )
    _asiento(
        client, "2023-06-01", "Venta",
        [{"cuenta": "570", "debe": 300}, {"cuenta": "700", "haber": 300}],
    )
    assert _cerrar(client, 2023).status_code == 200

    r = _abrir(client, 2024)
    assert r.status_code == 200
    datos = r.json()
    assert datos["abierto"] is True

    apertura = client.get(f"/api/v1/asientos/{datos['asiento_apertura_id']}").json()
    assert apertura["fecha"] == "2024-01-01"
    apuntes = {a["cuenta"]: a for a in apertura["apuntes"]}
    assert apuntes["572"]["debe"] == 1000
    assert apuntes["100"]["haber"] == 1000
    assert apuntes["570"]["debe"] == 300
    assert apuntes["129"]["haber"] == 300
    assert "700" not in apuntes  # ya absorbida en el resultado, no se reabre

    assert _saldo(client, "572") == 1000
    assert _saldo(client, "570") == 300
    assert _saldo(client, "129") == -300


def test_deshacer_cierre_y_apertura(client):
    _asiento(
        client, "2023-01-01", "Aportación",
        [{"cuenta": "572", "debe": 500}, {"cuenta": "100", "haber": 500}],
    )
    assert _cerrar(client, 2023).status_code == 200
    assert _abrir(client, 2024).status_code == 200

    assert client.delete("/api/v1/ejercicios/2023/cierre").status_code == 409

    assert client.delete("/api/v1/ejercicios/2024/apertura").status_code == 204
    assert client.get("/api/v1/ejercicios/2024").json()["abierto"] is False

    assert client.delete("/api/v1/ejercicios/2023/cierre").status_code == 204
    assert client.get("/api/v1/ejercicios/2023").json()["cerrado"] is False

    r = client.post(
        "/api/v1/asientos",
        json={
            "fecha": "2023-06-01",
            "concepto": "tras deshacer",
            "apuntes": [{"cuenta": "570", "debe": 10}, {"cuenta": "700", "haber": 10}],
        },
    )
    assert r.status_code == 201


def test_detalle_muestra_resultado_previsto_si_sigue_abierto(client):
    _asiento(
        client, "2023-01-01", "Venta",
        [{"cuenta": "570", "debe": 100}, {"cuenta": "700", "haber": 100}],
    )
    datos = client.get("/api/v1/ejercicios/2023").json()
    assert datos["cerrado"] is False
    assert datos["resultado_previsto"] == 100


def test_listar_incluye_los_anios_con_movimientos(client):
    _asiento(
        client, "2023-01-01", "Venta",
        [{"cuenta": "570", "debe": 100}, {"cuenta": "700", "haber": 100}],
    )
    anios = {e["anio"] for e in client.get("/api/v1/ejercicios").json()}
    assert 2023 in anios
