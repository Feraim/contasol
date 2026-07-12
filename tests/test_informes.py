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
    pn = b["pasivo"]["A) PATRIMONIO NETO · A-1) Fondos propios · VII. Resultado del ejercicio"]
    assert any(f["importe"] == 1300 for f in pn)  # resultado del periodo


def test_balance_clasifica_por_epigrafes_oficiales(client):
    for codigo, nombre in (
        ("206", "Aplicaciones informáticas"),
        ("217", "Equipos para procesos de información"),
        ("300", "Mercaderías"),
        ("170", "Deudas LP entidades de crédito"),
        ("520", "Deudas CP entidades de crédito"),
    ):
        r = client.post("/api/v1/cuentas", json={"codigo": codigo + "9", "nombre": nombre})
        assert r.status_code == 201, r.text

    client.post(
        "/api/v1/asientos",
        json={
            "fecha": "2026-01-02",
            "concepto": "Siembra balance",
            "apuntes": [
                {"cuenta": "2069", "debe": 100},   # inmovilizado intangible
                {"cuenta": "2179", "debe": 200},   # inmovilizado material
                {"cuenta": "3009", "debe": 150},   # existencias
                {"cuenta": "572", "debe": 550},
                {"cuenta": "1709", "haber": 300},  # deudas a largo plazo
                {"cuenta": "5209", "haber": 200},  # deudas a corto plazo
                {"cuenta": "400", "haber": 500},   # acreedores comerciales
            ],
        },
    )
    b = client.get("/api/v1/informes/balance?hasta=2026-12-31").json()
    assert b["cuadrado"] is True

    activo = b["activo"]
    assert any(f["cuenta"] == "2069" for f in activo["A) ACTIVO NO CORRIENTE · I. Inmovilizado intangible"])
    assert any(f["cuenta"] == "2179" for f in activo["A) ACTIVO NO CORRIENTE · II. Inmovilizado material"])
    assert any(f["cuenta"] == "3009" for f in activo["B) ACTIVO CORRIENTE · II. Existencias"])
    assert any(f["cuenta"] == "572" for f in activo["B) ACTIVO CORRIENTE · VII. Efectivo y otros activos líquidos equivalentes"])

    pasivo = b["pasivo"]
    assert any(f["cuenta"] == "1709" for f in pasivo["B) PASIVO NO CORRIENTE · II. Deudas a largo plazo"])
    assert any(f["cuenta"] == "5209" for f in pasivo["C) PASIVO CORRIENTE · II. Deudas a corto plazo"])
    assert any(
        f["cuenta"] == "400"
        for f in pasivo["C) PASIVO CORRIENTE · IV. Acreedores comerciales y otras cuentas a pagar"]
    )


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
