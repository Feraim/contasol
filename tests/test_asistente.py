import json

from contalibre.services import ia_tools


def _factura_emitida(client, tercero_id, importe_base=1000):
    r = client.post(
        "/api/v1/facturas",
        json={
            "tipo": "emitida",
            "numero": "F-IA-1",
            "fecha": "2026-03-01",
            "tercero_id": tercero_id,
            "lineas": [{"descripcion": "Servicios", "base": importe_base, "tipo_iva": 21}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_ejecutar_tool_desconocida_no_lanza():
    resultado = ia_tools.ejecutar_tool(None, "no_existe", {})
    assert "error" in resultado


def test_ejecutar_tool_argumentos_invalidos_no_lanza(client):
    resultado = ia_tools.ejecutar_tool(None, "informe_iva_trimestral", {"ejercicio": 2026})
    assert "error" in resultado  # falta 'trimestre'


def test_estado_ollama_no_disponible_en_este_entorno(client):
    r = client.get("/api/v1/ia/estado")
    assert r.status_code == 200
    body = r.json()
    assert body["disponible"] is False
    assert body["modelos_descargados"] == []


def test_preguntar_sin_ollama_devuelve_503(client):
    r = client.post("/api/v1/ia/preguntar", json={"pregunta": "¿cuánto tengo en el banco?"})
    assert r.status_code == 503


def test_asistente_ejecuta_herramientas_con_datos_reales(client, tercero, monkeypatch):
    factura = _factura_emitida(client, tercero["id"], importe_base=1000)

    llamadas = []

    def chat_simulado(mensajes, tools=None):
        llamadas.append(mensajes)
        if len(llamadas) == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "listar_facturas", "arguments": {"tipo": "emitida"}}}
                ],
            }
        ultimo = mensajes[-1]
        datos = json.loads(ultimo["content"])
        total = datos["resultado"][0]["total"]
        return {"role": "assistant", "content": f"Tienes una factura emitida por {total} €.", "tool_calls": []}

    monkeypatch.setattr("contalibre.ollama_client.chat", chat_simulado)

    r = client.post("/api/v1/ia/preguntar", json={"pregunta": "¿qué facturas emitidas tengo?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert str(factura["total"]) in body["respuesta"] or f"{factura['total']:.1f}" in body["respuesta"]
    assert body["herramientas_usadas"] == [
        {"herramienta": "listar_facturas", "argumentos": {"tipo": "emitida"}}
    ]


def test_asistente_encadena_varias_herramientas(client, tercero, monkeypatch):
    _factura_emitida(client, tercero["id"])

    respuestas = [
        {
            "role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": "resumen_panel", "arguments": {}}}],
        },
        {
            "role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": "informe_perdidas_y_ganancias", "arguments": {}}}],
        },
        {"role": "assistant", "content": "Resultado calculado a partir de dos consultas.", "tool_calls": []},
    ]
    llamadas = iter(respuestas)
    monkeypatch.setattr("contalibre.ollama_client.chat", lambda mensajes, tools=None: next(llamadas))

    r = client.post("/api/v1/ia/preguntar", json={"pregunta": "resume mi situación"})
    assert r.status_code == 200
    body = r.json()
    nombres = [h["herramienta"] for h in body["herramientas_usadas"]]
    assert nombres == ["resumen_panel", "informe_perdidas_y_ganancias"]
    assert body["respuesta"] == "Resultado calculado a partir de dos consultas."


def test_asistente_corta_tras_el_limite_de_iteraciones(client, monkeypatch):
    def chat_infinito(mensajes, tools=None):
        return {
            "role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": "resumen_panel", "arguments": {}}}],
        }

    monkeypatch.setattr("contalibre.ollama_client.chat", chat_infinito)

    r = client.post("/api/v1/ia/preguntar", json={"pregunta": "algo que nunca se resuelve"})
    assert r.status_code == 200
    body = r.json()
    assert "reformular" in body["respuesta"].lower()
    assert len(body["herramientas_usadas"]) == 6  # MAX_ITERACIONES


def test_asistente_respeta_el_aislamiento_multiempresa(client, tercero, monkeypatch):
    _factura_emitida(client, tercero["id"])

    def chat_lista_facturas(mensajes, tools=None):
        if len(mensajes) <= 2:
            return {
                "role": "assistant", "content": "",
                "tool_calls": [{"function": {"name": "listar_facturas", "arguments": {}}}],
            }
        datos = json.loads(mensajes[-1]["content"])
        return {"role": "assistant", "content": f"{len(datos['resultado'])} factura(s)", "tool_calls": []}

    monkeypatch.setattr("contalibre.ollama_client.chat", chat_lista_facturas)

    r = client.post("/api/v1/ia/preguntar", json={"pregunta": "¿cuántas facturas tengo?"})
    assert r.json()["respuesta"] == "1 factura(s)"

    from fastapi.testclient import TestClient

    from contalibre.main import app

    with TestClient(app) as otro:
        otro.post(
            "/api/v1/auth/registro",
            json={
                "email": "vecino-ia@contalibre.local",
                "password": "password1234",
                "empresa_nombre": "Empresa vecina IA",
            },
        )
        r2 = otro.post("/api/v1/ia/preguntar", json={"pregunta": "¿cuántas facturas tengo?"})
        assert r2.json()["respuesta"] == "0 factura(s)"
