from contalibre.services import norma43


def _linea22(fecha_op, fecha_valor, debe_haber, importe_centimos, documento="", ref1="", ref2=""):
    linea = "22"
    linea += "0000"  # banco
    linea += "0000"  # sucursal
    linea += fecha_op  # AAMMDD
    linea += fecha_valor  # AAMMDD
    linea += "01"  # concepto común
    linea += "001"  # concepto propio
    linea += debe_haber  # 1=debe/cargo, 2=haber/abono
    linea += str(importe_centimos).zfill(14)
    linea += documento.ljust(10)[:10]
    linea += ref1.ljust(12)[:12]
    linea += ref2.ljust(16)[:16]
    assert len(linea) == 80
    return linea


def _linea23(texto):
    return "23" + "01" + texto


def _asiento(client, fecha, concepto, apuntes):
    r = client.post("/api/v1/asientos", json={"fecha": fecha, "concepto": concepto, "apuntes": apuntes})
    assert r.status_code == 201, r.text
    return r.json()


def test_parsear_norma43_basico():
    contenido = "\n".join([
        _linea22("240310", "240310", "2", 100000, "DOC1", "TRANSF", "NOMINA"),
        _linea23("Texto ampliado del abono"),
        _linea22("240312", "240312", "1", 5000, "DOC2", "COMISION", "MANTENIMIENTO"),
    ])
    movimientos = norma43.parsear(contenido)
    assert len(movimientos) == 2

    abono = movimientos[0]
    assert abono.importe == 100000
    assert abono.documento == "DOC1"
    assert "TRANSF" in abono.concepto
    assert "Texto ampliado del abono" in abono.concepto

    cargo = movimientos[1]
    assert cargo.importe == -5000
    assert cargo.documento == "DOC2"


def test_parsear_fichero_sin_movimientos_falla():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        norma43.parsear("11 cabecera de cuenta sin movimientos\n88 totales")


def test_importar_cuenta_inexistente(client):
    contenido = _linea22("240310", "240310", "2", 100000)
    r = client.post(
        "/api/v1/bancos/importar",
        json={"cuenta_tesoreria": "999999", "contenido": contenido},
    )
    assert r.status_code == 422


def test_importar_concilia_automaticamente_con_apunte_existente(client):
    _asiento(
        client, "2024-03-10", "Cobro nómina",
        [{"cuenta": "572", "debe": 1000}, {"cuenta": "700", "haber": 1000}],
    )
    contenido = _linea22("240310", "240310", "2", 100000, "DOC1", "TRANSFERENCIA")
    r = client.post(
        "/api/v1/bancos/importar", json={"cuenta_tesoreria": "572", "contenido": contenido}
    )
    assert r.status_code == 201, r.text
    movimientos = r.json()
    assert len(movimientos) == 1
    assert movimientos[0]["conciliado"] is True
    assert movimientos[0]["importe"] == 1000


def test_importar_sin_apunte_queda_pendiente(client):
    contenido = _linea22("240312", "240312", "1", 5000, "DOC2", "COMISION")
    r = client.post(
        "/api/v1/bancos/importar", json={"cuenta_tesoreria": "572", "contenido": contenido}
    )
    assert r.status_code == 201, r.text
    m = r.json()[0]
    assert m["conciliado"] is False
    assert m["importe"] == -50

    pendientes = client.get(
        "/api/v1/bancos/movimientos", params={"cuenta": "572", "conciliado": "false"}
    ).json()
    assert any(x["id"] == m["id"] for x in pendientes)


def test_no_reimporta_duplicados(client):
    contenido = _linea22("240312", "240312", "1", 5000, "DOC2", "COMISION")
    r1 = client.post("/api/v1/bancos/importar", json={"cuenta_tesoreria": "572", "contenido": contenido})
    assert len(r1.json()) == 1
    r2 = client.post("/api/v1/bancos/importar", json={"cuenta_tesoreria": "572", "contenido": contenido})
    assert r2.json() == []  # ya estaba importado, no se duplica
    todos = client.get("/api/v1/bancos/movimientos", params={"cuenta": "572"}).json()
    assert len(todos) == 1


def test_conciliar_manual(client):
    asiento = _asiento(
        client, "2024-05-01", "Pago proveedor",
        [{"cuenta": "400", "debe": 200}, {"cuenta": "572", "haber": 200}],
    )
    apunte_572 = next(a for a in asiento["apuntes"] if a["cuenta"] == "572")

    contenido = _linea22("240502", "240502", "1", 20000, "DOC3")  # fecha distinta -> no auto-concilia
    r = client.post("/api/v1/bancos/importar", json={"cuenta_tesoreria": "572", "contenido": contenido})
    m = r.json()[0]
    assert m["conciliado"] is False

    rc = client.post(f"/api/v1/bancos/{m['id']}/conciliar", json={"apunte_id": apunte_572["id"]})
    assert rc.status_code == 200, rc.text
    assert rc.json()["conciliado"] is True


def test_conciliar_manual_rechaza_importe_distinto(client):
    asiento = _asiento(
        client, "2024-05-01", "Pago proveedor",
        [{"cuenta": "400", "debe": 200}, {"cuenta": "572", "haber": 200}],
    )
    apunte_572 = next(a for a in asiento["apuntes"] if a["cuenta"] == "572")

    contenido = _linea22("240502", "240502", "1", 5000, "DOC4")  # 50€, no coincide con 200€
    r = client.post("/api/v1/bancos/importar", json={"cuenta_tesoreria": "572", "contenido": contenido})
    m = r.json()[0]

    rc = client.post(f"/api/v1/bancos/{m['id']}/conciliar", json={"apunte_id": apunte_572["id"]})
    assert rc.status_code == 422


def test_conciliar_creando_asiento_nuevo(client):
    contenido = _linea22("240312", "240312", "1", 5000, "DOC2", "COMISION BANCARIA")
    r = client.post("/api/v1/bancos/importar", json={"cuenta_tesoreria": "572", "contenido": contenido})
    m = r.json()[0]
    assert m["conciliado"] is False

    rc = client.post(
        f"/api/v1/bancos/{m['id']}/conciliar-nuevo",
        json={"cuenta_contrapartida": "626", "concepto": "Comisión bancaria"},
    )
    assert rc.status_code == 200, rc.text
    m2 = rc.json()
    assert m2["conciliado"] is True

    apunte_id = m2["apunte_id"]
    asiento_id = None
    for a in client.get("/api/v1/asientos", params={"cuenta": "572"}).json():
        for ap in a["apuntes"]:
            if ap["id"] == apunte_id:
                asiento_id = a["id"]
    asiento = client.get(f"/api/v1/asientos/{asiento_id}").json()
    apuntes = {a["cuenta"]: a for a in asiento["apuntes"]}
    assert apuntes["572"]["haber"] == 50
    assert apuntes["626"]["debe"] == 50


def test_desconciliar_y_eliminar(client):
    _asiento(
        client, "2024-03-10", "Cobro",
        [{"cuenta": "572", "debe": 1000}, {"cuenta": "700", "haber": 1000}],
    )
    contenido = _linea22("240310", "240310", "2", 100000, "DOC1")
    r = client.post("/api/v1/bancos/importar", json={"cuenta_tesoreria": "572", "contenido": contenido})
    m = r.json()[0]
    assert m["conciliado"] is True

    assert client.delete(f"/api/v1/bancos/{m['id']}").status_code == 409  # conciliado, no se puede borrar

    rd = client.delete(f"/api/v1/bancos/{m['id']}/conciliacion")
    assert rd.status_code == 200
    assert rd.json()["conciliado"] is False

    assert client.delete(f"/api/v1/bancos/{m['id']}").status_code == 204
