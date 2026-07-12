"""Cliente HTTP mínimo para un servidor Ollama local.

No es un SDK genérico: solo cubre lo que necesita el asistente de IA
(`/api/chat` con tool calling y `/api/tags` para comprobar qué modelos
hay descargados). Ollama debe estar instalado y en marcha aparte
(`ollama serve`, normalmente automático); esta aplicación nunca lo
instala ni lo lanza.
"""

import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5")
TIMEOUT_CHAT = 180.0
TIMEOUT_ESTADO = 5.0


class OllamaNoDisponible(Exception):
    """Ollama no responde en OLLAMA_URL (no está instalado o no está arrancado)."""


def chat(mensajes: list[dict], tools: list[dict] | None = None) -> dict:
    """Llama a POST /api/chat y devuelve el mensaje del asistente (dict)."""
    cuerpo = {"model": OLLAMA_MODEL, "messages": mensajes, "stream": False}
    if tools:
        cuerpo["tools"] = tools
    try:
        with httpx.Client(timeout=TIMEOUT_CHAT) as cliente:
            r = cliente.post(f"{OLLAMA_URL}/api/chat", json=cuerpo)
    except httpx.ConnectError as exc:
        raise OllamaNoDisponible(
            f"No se puede conectar con Ollama en {OLLAMA_URL}. "
            "¿Está instalado y arrancado ('ollama serve')?"
        ) from exc
    if r.status_code == 404:
        raise OllamaNoDisponible(
            f"El modelo '{OLLAMA_MODEL}' no está descargado. Ejecuta: ollama pull {OLLAMA_MODEL}"
        )
    r.raise_for_status()
    return r.json()["message"]


def estado() -> dict:
    """Comprueba si Ollama responde y si el modelo configurado está descargado."""
    try:
        with httpx.Client(timeout=TIMEOUT_ESTADO) as cliente:
            r = cliente.get(f"{OLLAMA_URL}/api/tags")
        r.raise_for_status()
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        return {"disponible": False, "url": OLLAMA_URL, "modelo": OLLAMA_MODEL, "modelos_descargados": []}
    modelos = [m["name"] for m in r.json().get("models", [])]
    modelo_base = OLLAMA_MODEL.split(":")[0]
    return {
        "disponible": True,
        "url": OLLAMA_URL,
        "modelo": OLLAMA_MODEL,
        "modelo_descargado": any(m == OLLAMA_MODEL or m.split(":")[0] == modelo_base for m in modelos),
        "modelos_descargados": modelos,
    }
