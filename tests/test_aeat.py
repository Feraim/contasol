def _tercero(client, tipo, nif, nombre):
    r = client.post("/api/v1/terceros", json={"tipo": tipo, "nif": nif, "nombre": nombre})
    assert r.status_code == 201, r.text
    return r.json()


def _factura(client, tipo, numero, fecha, tercero_id, lineas, **extra):
    r = client.post(
        "/api/v1/facturas",
        json={"tipo": tipo, "numero": numero, "fecha": fecha, "tercero_id": tercero_id,
              "lineas": lineas, **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _preparar_ejercicio(client):
    cliente = _tercero(client, "cliente", "B11111111", "Cliente Grande SL")
    proveedor_pequeno = _tercero(client, "proveedor", "B22222222", "Proveedor Pequeño SL")
    proveedor_grande = _tercero(client, "proveedor", "B33333333", "Proveedor Grande SL")

    # T1 2023: venta 1000 @21% = 210 cuota; compra 400 @21% = 84 cuota
    _factura(client, "emitida", "F-2023-1", "2023-01-15", cliente["id"],
              [{"descripcion": "Servicios", "base": 1000, "tipo_iva": 21}])
    _factura(client, "recibida", "R-2023-1", "2023-02-10", proveedor_pequeno["id"],
              [{"descripcion": "Suministros", "base": 400, "tipo_iva": 21}])

    # T2 2023: venta 2000 @10% = 200 cuota (mismo cliente, para superar el umbral 347 anual)
    _factura(client, "emitida", "F-2023-2", "2023-04-20", cliente["id"],
              [{"descripcion": "Material", "base": 2000, "tipo_iva": 10}])

    # T3 2023: compra grande sin IVA (proveedor_grande), supera el umbral 347
    _factura(client, "recibida", "R-2023-2", "2023-07-05", proveedor_grande["id"],
              [{"descripcion": "Terreno", "base": 3200, "tipo_iva": 0}])

    return cliente, proveedor_pequeno, proveedor_grande


def test_modelo_303_trimestre(client):
    _preparar_ejercicio(client)
    r = client.get("/api/v1/aeat/303", params={"ejercicio": 2023, "trimestre": 1})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["iva_devengado"]["casilla_27_cuota_devengada"] == 210
    assert m["iva_deducible"]["casilla_28_base"] == 400
    assert m["iva_deducible"]["casilla_29_cuota"] == 84
    assert m["casilla_46_resultado_regimen_general"] == 126
    assert m["casilla_69_resultado_liquidacion"] == 126
    assert m["sentido"] == "a ingresar"


def test_modelo_303_a_compensar_si_negativo_y_no_es_ultimo_trimestre(client):
    _preparar_ejercicio(client)
    r = client.get("/api/v1/aeat/303", params={"ejercicio": 2023, "trimestre": 3})
    m = r.json()
    # T3: solo la compra grande sin IVA -> cuota deducible 0, devengada 0
    assert m["casilla_69_resultado_liquidacion"] == 0
    assert m["sentido"] == "sin actividad"


def test_modelo_390_agrega_los_cuatro_trimestres(client):
    _preparar_ejercicio(client)
    r = client.get("/api/v1/aeat/390", params={"ejercicio": 2023})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["total_devengado"] == 410  # 210 + 200
    assert m["total_deducible"] == 84
    assert m["resultado_anual"] == 326
    resultados = {x["trimestre"]: x["resultado"] for x in m["resultados_trimestrales"]}
    assert resultados[1] == 126
    assert resultados[2] == 200
    assert resultados[3] == 0
    assert resultados[4] == 0


def test_modelo_347_umbral_y_claves(client):
    cliente, proveedor_pequeno, proveedor_grande = _preparar_ejercicio(client)
    r = client.get("/api/v1/aeat/347", params={"ejercicio": 2023})
    assert r.status_code == 200, r.text
    m = r.json()
    registros = {r["nif"]: r for r in m["registros"]}

    assert proveedor_pequeno["nif"] not in registros  # 484 € < 3.005,06 €

    assert cliente["nif"] in registros
    assert registros[cliente["nif"]]["clave"] == "B"
    assert registros[cliente["nif"]]["operacion"] == "ventas"
    assert registros[cliente["nif"]]["importe_anual"] == 3410  # 1210 + 2200
    assert registros[cliente["nif"]]["trimestres"]["1"] == 1210
    assert registros[cliente["nif"]]["trimestres"]["2"] == 2200

    assert proveedor_grande["nif"] in registros
    assert registros[proveedor_grande["nif"]]["clave"] == "A"
    assert registros[proveedor_grande["nif"]]["operacion"] == "compras"
    assert registros[proveedor_grande["nif"]]["importe_anual"] == 3200


def test_exportacion_pdf_y_excel_aeat(client):
    _preparar_ejercicio(client)
    for modelo, params in (
        ("303", {"ejercicio": 2023, "trimestre": 1}),
        ("390", {"ejercicio": 2023}),
        ("347", {"ejercicio": 2023}),
    ):
        rpdf = client.get(f"/api/v1/aeat/{modelo}", params={**params, "formato": "pdf"})
        assert rpdf.status_code == 200
        assert rpdf.headers["content-type"] == "application/pdf"
        assert len(rpdf.content) > 100

        rxls = client.get(f"/api/v1/aeat/{modelo}", params={**params, "formato": "excel"})
        assert rxls.status_code == 200
        assert "spreadsheetml" in rxls.headers["content-type"]
        assert len(rxls.content) > 100


def test_exportacion_pdf_y_excel_informes(client):
    _preparar_ejercicio(client)
    casos = [
        ("/api/v1/informes/mayor", {"cuenta": "700"}),
        ("/api/v1/informes/sumas-saldos", {}),
        ("/api/v1/informes/pyg", {}),
        ("/api/v1/informes/balance", {}),
    ]
    for ruta, params in casos:
        rpdf = client.get(ruta, params={**params, "formato": "pdf"})
        assert rpdf.status_code == 200, rpdf.text
        assert rpdf.headers["content-type"] == "application/pdf"

        rxls = client.get(ruta, params={**params, "formato": "excel"})
        assert rxls.status_code == 200, rxls.text
        assert "spreadsheetml" in rxls.headers["content-type"]
