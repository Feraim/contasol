def _emitida(tercero_id, numero="F-001", **extra):
    return {
        "tipo": "emitida",
        "numero": numero,
        "fecha": "2026-02-10",
        "tercero_id": tercero_id,
        "lineas": [
            {"descripcion": "Servicios", "base": 1000, "tipo_iva": 21},
            {"descripcion": "Material", "base": 500, "tipo_iva": 10},
        ],
        **extra,
    }


def test_factura_emitida_genera_asiento(client, tercero):
    r = client.post("/api/v1/facturas", json=_emitida(tercero["id"]))
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["base_total"] == 1500
    assert f["cuota_iva"] == 260  # 210 + 50
    assert f["total"] == 1760

    asiento = client.get(f"/api/v1/asientos/{f['asiento_id']}").json()
    apuntes = {a["cuenta"]: a for a in asiento["apuntes"]}
    subcuenta = f"430{tercero['id']:04d}"
    assert apuntes[subcuenta]["debe"] == 1760
    assert apuntes["700"]["haber"] == 1500
    assert apuntes["477"]["haber"] == 260

    # La subcuenta del cliente queda creada y asociada al tercero
    terceros = client.get("/api/v1/terceros").json()
    assert terceros[0]["cuenta_cliente"] == subcuenta


def test_factura_recibida_con_retencion(client, tercero):
    r = client.post(
        "/api/v1/facturas",
        json={
            "tipo": "recibida",
            "numero": "R-77",
            "fecha": "2026-02-15",
            "tercero_id": tercero["id"],
            "cuenta_contrapartida": "623",
            "retencion_pct": 15,
            "lineas": [{"descripcion": "Asesoría", "base": 1000, "tipo_iva": 21}],
        },
    )
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["retencion_importe"] == 150
    assert f["total"] == 1210

    apuntes = {
        a["cuenta"]: a
        for a in client.get(f"/api/v1/asientos/{f['asiento_id']}").json()["apuntes"]
    }
    assert apuntes["623"]["debe"] == 1000
    assert apuntes["472"]["debe"] == 210
    assert apuntes[f"400{tercero['id']:04d}"]["haber"] == 1060  # total - retención
    assert apuntes["4751"]["haber"] == 150


def test_numero_duplicado_rechazado(client, tercero):
    assert client.post("/api/v1/facturas", json=_emitida(tercero["id"])).status_code == 201
    assert client.post("/api/v1/facturas", json=_emitida(tercero["id"])).status_code == 409


def test_liquidar_factura(client, tercero):
    f = client.post("/api/v1/facturas", json=_emitida(tercero["id"])).json()
    r = client.post(
        f"/api/v1/facturas/{f['id']}/liquidar",
        json={"fecha": "2026-03-01", "cuenta_tesoreria": "572"},
    )
    assert r.status_code == 200, r.text
    f2 = r.json()
    assert f2["estado"] == "pagada"

    apuntes = {
        a["cuenta"]: a
        for a in client.get(f"/api/v1/asientos/{f2['asiento_pago_id']}").json()["apuntes"]
    }
    assert apuntes["572"]["debe"] == 1760

    # No se puede liquidar dos veces
    r = client.post(
        f"/api/v1/facturas/{f['id']}/liquidar", json={"fecha": "2026-03-02"}
    )
    assert r.status_code == 409


def test_asiento_de_factura_protegido(client, tercero):
    f = client.post("/api/v1/facturas", json=_emitida(tercero["id"])).json()
    assert client.delete(f"/api/v1/asientos/{f['asiento_id']}").status_code == 409


def test_eliminar_factura_borra_asientos(client, tercero):
    f = client.post("/api/v1/facturas", json=_emitida(tercero["id"])).json()
    client.post(f"/api/v1/facturas/{f['id']}/liquidar", json={"fecha": "2026-03-01"})
    f = client.get(f"/api/v1/facturas/{f['id']}").json()
    assert client.delete(f"/api/v1/facturas/{f['id']}").status_code == 204
    assert client.get(f"/api/v1/asientos/{f['asiento_id']}").status_code == 404
    assert client.get(f"/api/v1/asientos/{f['asiento_pago_id']}").status_code == 404


def test_resumen_iva(client, tercero):
    client.post("/api/v1/facturas", json=_emitida(tercero["id"]))
    client.post(
        "/api/v1/facturas",
        json={
            "tipo": "recibida",
            "numero": "R-1",
            "fecha": "2026-01-20",
            "tercero_id": tercero["id"],
            "lineas": [{"descripcion": "Compras", "base": 200, "tipo_iva": 21}],
        },
    )
    iva = client.get("/api/v1/informes/iva?ejercicio=2026&trimestre=1").json()
    assert iva["repercutido"]["cuota"] == 260
    assert iva["soportado"]["cuota"] == 42
    assert iva["resultado"] == 218
    assert iva["sentido"] == "a ingresar"
