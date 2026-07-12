from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import insert

from contalibre import database, models, models_control
from contalibre.main import app


def _registrar(cliente, email, empresa_nombre, password="password1234"):
    r = cliente.post(
        "/api/v1/auth/registro",
        json={"email": email, "password": password, "nombre": email, "empresa_nombre": empresa_nombre},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_registro_crea_sesion_y_empresa(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200, r.text
    perfil = r.json()
    assert perfil["email"] == "demo@contalibre.local"
    assert len(perfil["empresas"]) == 1
    assert perfil["empresas"][0]["rol"] == "admin"
    assert perfil["empresas"][0]["nombre"] == "Empresa Demo"


def test_login_credenciales_invalidas(client):
    client.cookies.clear()
    r = client.post(
        "/api/v1/auth/login", json={"email": "demo@contalibre.local", "password": "mala"}
    )
    assert r.status_code == 401


def test_sin_sesion_rechaza_acceso(client):
    client.cookies.clear()
    r = client.get("/api/v1/cuentas")
    assert r.status_code == 401


def test_logout_invalida_la_sesion(client):
    assert client.get("/api/v1/auth/me").status_code == 200
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_aislamiento_de_datos_entre_empresas(client):
    # `client` ya está registrado como admin de "Empresa Demo".
    r = client.post(
        "/api/v1/terceros", json={"tipo": "cliente", "nif": "B00000001", "nombre": "Solo de Empresa Demo"}
    )
    assert r.status_code == 201, r.text

    with TestClient(app) as otro:
        _registrar(otro, "vecino@contalibre.local", "Empresa Vecina")
        terceros_vecino = otro.get("/api/v1/terceros").json()
        assert terceros_vecino == []  # no ve nada de la otra empresa

        # el PGC se precarga de forma independiente para cada empresa
        cuentas_vecino = otro.get("/api/v1/cuentas").json()
        assert any(c["codigo"] == "572" for c in cuentas_vecino)

        otro.post(
            "/api/v1/terceros", json={"tipo": "cliente", "nif": "B00000002", "nombre": "Solo de Empresa Vecina"}
        )

    # el cliente original nunca ve al tercero de la empresa vecina
    terceros_demo = client.get("/api/v1/terceros").json()
    nombres = {t["nombre"] for t in terceros_demo}
    assert nombres == {"Solo de Empresa Demo"}


def test_segunda_empresa_del_mismo_usuario_esta_aislada(client):
    r = client.post("/api/v1/empresas", json={"nombre": "Segunda empresa", "nif": ""})
    assert r.status_code == 201, r.text
    segunda_id = r.json()["id"]

    client.post("/api/v1/terceros", json={"tipo": "cliente", "nif": "B11111111", "nombre": "Cliente empresa 1"})

    # Cambiar de empresa activa vía la cabecera X-Empresa-Id
    terceros_segunda = client.get("/api/v1/terceros", headers={"X-Empresa-Id": str(segunda_id)}).json()
    assert terceros_segunda == []

    client.post(
        "/api/v1/terceros",
        json={"tipo": "cliente", "nif": "B22222222", "nombre": "Cliente empresa 2"},
        headers={"X-Empresa-Id": str(segunda_id)},
    )
    terceros_empresa1 = client.get("/api/v1/terceros").json()
    assert {t["nombre"] for t in terceros_empresa1} == {"Cliente empresa 1"}


def test_no_se_puede_usar_una_empresa_ajena(client):
    with TestClient(app) as otro:
        perfil = _registrar(otro, "ajeno@contalibre.local", "Empresa Ajena")
        empresa_ajena_id = perfil["empresas"][0]["id"]

    r = client.get("/api/v1/terceros", headers={"X-Empresa-Id": str(empresa_ajena_id)})
    assert r.status_code == 403


def test_invitar_usuario_y_roles(client):
    perfil = client.get("/api/v1/auth/me").json()
    empresa_id = perfil["empresas"][0]["id"]

    with TestClient(app) as invitado:
        _registrar(invitado, "invitado@contalibre.local", "Empresa del invitado")

    r = client.post(
        f"/api/v1/empresas/{empresa_id}/usuarios",
        json={"email": "invitado@contalibre.local", "rol": "editor"},
    )
    assert r.status_code == 201, r.text

    usuarios = client.get(f"/api/v1/empresas/{empresa_id}/usuarios").json()
    roles = {u["email"]: u["rol"] for u in usuarios}
    assert roles["invitado@contalibre.local"] == "editor"
    assert roles["demo@contalibre.local"] == "admin"

    # El invitado ya puede operar sobre la empresa demo usando su propia sesión
    with TestClient(app) as invitado2:
        r = invitado2.post(
            "/api/v1/auth/login", json={"email": "invitado@contalibre.local", "password": "password1234"}
        )
        assert r.status_code == 200
        terceros = invitado2.get("/api/v1/terceros", headers={"X-Empresa-Id": str(empresa_id)})
        assert terceros.status_code == 200

        # Pero un editor no puede invitar a otros usuarios
        r2 = invitado2.post(
            f"/api/v1/empresas/{empresa_id}/usuarios",
            json={"email": "demo@contalibre.local", "rol": "admin"},
            headers={"X-Empresa-Id": str(empresa_id)},
        )
        assert r2.status_code == 403


def test_migracion_de_instalacion_antigua(tmp_path):
    # Fichero de una instalación previa a multiempresa, con el esquema de siempre.
    legacy_path = tmp_path / "contalibre_antigua.db"
    engine = database._crear_engine(legacy_path)
    database.Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(insert(models.Cuenta).values(codigo="572", nombre="Bancos"))
        conn.execute(insert(models.Asiento).values(numero=1, fecha=date(2024, 1, 1), concepto="Apertura"))
        conn.commit()

    database.reset_para_pruebas(tmp_path / "data")
    database.LEGACY_DB_PATH = legacy_path
    database.init_control_db()

    with database.ControlSession() as db:
        empresa_migrada = db.get(models_control.Empresa, 1)
        assert empresa_migrada is not None
        assert empresa_migrada.nombre == "Empresa migrada"

    with database.sesion_empresa(1) as db:
        asientos = db.query(models.Asiento).all()
        assert len(asientos) == 1
        assert asientos[0].concepto == "Apertura"
        cuentas = {c.codigo for c in db.query(models.Cuenta).all()}
        assert "572" in cuentas

    # El primer usuario que se registra tras la migración reclama la
    # empresa huérfana (además de crear la suya propia).
    with TestClient(app) as c:
        perfil = _registrar(c, "primero@contalibre.local", "Mi empresa nueva")
        nombres = {e["nombre"] for e in perfil["empresas"]}
        assert nombres == {"Mi empresa nueva", "Empresa migrada"}
        roles = {e["nombre"]: e["rol"] for e in perfil["empresas"]}
        assert roles["Empresa migrada"] == "admin"


def test_exportar_copia_de_seguridad(client):
    import sqlite3
    import zipfile
    from io import BytesIO

    client.post(
        "/api/v1/terceros", json={"tipo": "cliente", "nif": "B44444444", "nombre": "Para el backup"}
    )
    perfil = client.get("/api/v1/auth/me").json()
    empresa_id = perfil["empresas"][0]["id"]

    r = client.get(f"/api/v1/empresas/{empresa_id}/exportar")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(BytesIO(r.content)) as zf:
        nombres = zf.namelist()
        assert len(nombres) == 1
        contenido_db = zf.read(nombres[0])

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "copia.db"
        ruta.write_bytes(contenido_db)
        con = sqlite3.connect(ruta)
        filas = con.execute("SELECT nombre FROM terceros").fetchall()
        con.close()
    assert ("Para el backup",) in filas


def test_exportar_copia_solo_admin(client):
    perfil = client.get("/api/v1/auth/me").json()
    empresa_id = perfil["empresas"][0]["id"]

    with TestClient(app) as invitado:
        _registrar(invitado, "invitado_backup@contalibre.local", "Empresa del invitado backup")

    client.post(
        f"/api/v1/empresas/{empresa_id}/usuarios",
        json={"email": "invitado_backup@contalibre.local", "rol": "editor"},
    )

    with TestClient(app) as invitado2:
        invitado2.post(
            "/api/v1/auth/login",
            json={"email": "invitado_backup@contalibre.local", "password": "password1234"},
        )
        r = invitado2.get(
            f"/api/v1/empresas/{empresa_id}/exportar", headers={"X-Empresa-Id": str(empresa_id)}
        )
        assert r.status_code == 403


def test_registro_email_duplicado(client):
    r = client.post(
        "/api/v1/auth/registro",
        json={
            "email": "demo@contalibre.local",
            "password": "password1234",
            "empresa_nombre": "Otra vez",
        },
    )
    assert r.status_code == 409
