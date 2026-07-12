"""Orquestación del asistente de IA: bucle de tool calling contra Ollama."""

import json

from .. import ollama_client
from . import ia_tools

MAX_ITERACIONES = 6

SYSTEM_PROMPT_BASE = (
    "Eres el asistente contable de ContaLibre, un software de contabilidad para "
    "pymes y autónomos españoles. Respondes preguntas sobre los datos de la empresa "
    "activa usando EXCLUSIVAMENTE las herramientas disponibles: nunca inventes cifras "
    "ni asientos. Si necesitas datos, llama primero a la herramienta correspondiente; "
    "si una pregunta requiere varias consultas (comparar periodos, cruzar facturas con "
    "el mayor...), encadena las llamadas que hagan falta antes de responder. Cuando "
    "tengas la información, responde en español, de forma clara y concisa, citando las "
    "cifras exactas devueltas por las herramientas (en euros). Si los datos disponibles "
    "no permiten responder con certeza, dilo explícitamente en vez de inventar."
)


def _mensaje_sistema() -> dict:
    contenido = (
        f"{SYSTEM_PROMPT_BASE}\n\nEsquema de datos:\n"
        f"{json.dumps(ia_tools.DESCRIPCION_ESQUEMA, ensure_ascii=False)}"
    )
    return {"role": "system", "content": contenido}


def responder(db, pregunta: str, historial: list[dict] | None = None) -> dict:
    """Resuelve una pregunta en lenguaje natural sobre los datos contables.

    Devuelve {"respuesta": str, "herramientas_usadas": [...]}. `historial`
    permite continuar una conversación (lista de mensajes previos
    role/content, sin el nuevo system prompt).
    """
    mensajes = [_mensaje_sistema(), *(historial or []), {"role": "user", "content": pregunta}]
    herramientas_usadas: list[dict] = []

    for _ in range(MAX_ITERACIONES):
        mensaje = ollama_client.chat(mensajes, tools=ia_tools.TOOL_SCHEMAS)
        tool_calls = mensaje.get("tool_calls") or []
        if not tool_calls:
            return {
                "respuesta": mensaje.get("content", "").strip(),
                "herramientas_usadas": herramientas_usadas,
            }
        mensajes.append(mensaje)
        for llamada in tool_calls:
            nombre = llamada["function"]["name"]
            argumentos = llamada["function"].get("arguments") or {}
            resultado = ia_tools.ejecutar_tool(db, nombre, argumentos)
            herramientas_usadas.append({"herramienta": nombre, "argumentos": argumentos})
            mensajes.append(
                {"role": "tool", "content": json.dumps(resultado, ensure_ascii=False, default=str)}
            )

    return {
        "respuesta": (
            "No he podido completar la respuesta tras varias consultas encadenadas; "
            "prueba a reformular la pregunta de forma más concreta."
        ),
        "herramientas_usadas": herramientas_usadas,
    }
