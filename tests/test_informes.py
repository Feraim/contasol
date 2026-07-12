def _sembrar(client, tercero):
    # Capital inicial: 3000 € al banco
    client.post(
        "/api/v1/asientos",
        json={
            "fecha": "2026-01-02",
            "concepto": "Aportación inicial",
            "apuntes": [
                {"cuenta": "572", "debe": 3000},
                {"cuenta": "100", "haber": 3000},
            ],
        },
    )
    # Venta de 1500 + 260 de IVA
    client.post(
        "/api/v1/facturas",
        json={
            "tipo": "emitida",
            "numero": "F-1",
            "fecha": "2026-02-10",
            "tercero_id": tercero["id"],
            "lineas": [
                {"descripcion": "Servicios", "base": 1000, "tipo_iva": 21},
                {"descripcion": "Material", "base": 500, "tipo_iva": 10},
            ],
        },
    )
    # Gasto de 200 + 42 de IVA
    client.post(
        "/api/v1/facturas",
        json={
            "tipo": "recibida",
            "numero": "R-1",
            "fecha": "2026-02-15",
            "tercero_id": tercero["id"],
            "cuenta_contrapartida": "629",
            "lineas": [{"descripcion": "Suministros", "base": 200, "tipo_iva": 21}],
        },
    )


def test_sumas_y_saldos_cuadra(client, tercero):
    _sembrar(client, tercero)
    s = client.get("/api/v1/informes/sumas-saldos").json()
    assert s["cuadrado"] is True
    assert s["total_debe"] == s["total_haber"]


def test_pyg(client, tercero):
    _sembrar(client, tercero)
    p = client.get("/api/v1/informes/pyg?desde=2026-01-01&hasta=2026-12-31").json()
    assert p["total_ingresos"] == 1500
    assert p["total_gastos"] == 200
    assert p["resultado"] == 1300


def test_balance_cuadra(client, tercero):
    _sembrar(client, tercero)
    b = client.get("/api/v1/informes/balance?hasta=2026-12-31").json()
    assert b["cuadrado"] is True
    assert b["total_activo"] == b["total_pasivo"]
    pn = b["pasivo"]["Patrimonio neto"]
    assert any(f["importe"] == 1300 for f in pn)  # resultado del periodo


def test_mayor_con_saldo_acumulado(client, tercero):
    _sembrar(client, tercero)
    m = client.get("/api/v1/informes/mayor?cuenta=572").json()
    assert m["saldo"] == 3000
    assert m["movimientos"][0]["saldo"] == 3000


def test_panel_y_contexto_ia(client, tercero):
    _sembrar(client, tercero)
    panel = client.get("/api/v1/informes/panel").json()
    assert panel["num_asientos"] == 3

    ctx = client.get("/api/v1/ia/contexto").json()
    assert ctx["estadisticas"]["asientos"] == 3
    assert "endpoints_consulta" in ctx["esquema"]
