"""Punto de integración para un modelo de IA local.

Un LLM que corre en la máquina del usuario vía Ollama recibe el esquema de
`GET /api/v1/ia/contexto` y responde preguntas en `POST /api/v1/ia/preguntar`
usando tool calling contra los datos de la empresa activa (ver
services/ia_tools.py y services/asistente.py). ContaLibre no instala ni
arranca Ollama: solo se conecta a él si ya está en marcha.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, ollama_client, schemas
from ..deps import get_db
from ..services import asistente as svc_asistente
from ..services import ia_tools

router = APIRouter(prefix="/ia", tags=["ia"])

ENDPOINTS_CONSULTA = {
    "GET /api/v1/cuentas?q=": "buscar cuentas",
    "GET /api/v1/asientos?desde=&hasta=&cuenta=": "diario",
    "GET /api/v1/terceros?q=&tipo=": "clientes y proveedores",
    "GET /api/v1/facturas?tipo=&estado=&desde=&hasta=": "facturación",
    "GET /api/v1/activos": "inmovilizado y amortizaciones",
    "GET /api/v1/informes/mayor?cuenta=&desde=&hasta=": "libro mayor (acepta prefijo de cuenta)",
    "GET /api/v1/informes/sumas-saldos?desde=&hasta=": "balance de sumas y saldos",
    "GET /api/v1/informes/pyg?desde=&hasta=": "cuenta de pérdidas y ganancias",
    "GET /api/v1/informes/balance?hasta=": "balance de situación",
    "GET /api/v1/informes/iva?ejercicio=&trimestre=": "resumen de IVA (estilo modelo 303)",
    "GET /api/v1/informes/panel": "resumen general",
    "GET /api/v1/ejercicios": "estado de cierre/apertura de cada año",
    "GET /api/v1/ejercicios/{anio}": "detalle de un ejercicio (resultado previsto si sigue abierto)",
    "GET /api/v1/aeat/303?ejercicio=&trimestre=": "modelo 303 simplificado (casillas de IVA trimestral)",
    "GET /api/v1/aeat/390?ejercicio=": "modelo 390 simplificado (resumen anual de IVA)",
    "GET /api/v1/aeat/347?ejercicio=": "modelo 347 simplificado (operaciones con terceros >3.005,06 €)",
    "GET /api/v1/bancos/movimientos?cuenta=&conciliado=&desde=&hasta=": "movimientos bancarios importados",
    "GET /openapi.json": "especificación OpenAPI completa",
}
EXPORTACION = (
    "los informes (mayor, sumas-saldos, pyg, balance) y los modelos aeat/* aceptan "
    "?formato=pdf|excel para descargar el documento en vez de JSON"
)


@router.get("/contexto")
def contexto(db: Session = Depends(get_db)):
    """Esquema de datos + estadísticas, pensado como contexto para un LLM local."""
    stats = {
        "cuentas": db.scalar(select(func.count()).select_from(models.Cuenta)),
        "asientos": db.scalar(select(func.count()).select_from(models.Asiento)),
        "terceros": db.scalar(select(func.count()).select_from(models.Tercero)),
        "facturas": db.scalar(select(func.count()).select_from(models.Factura)),
        "activos": db.scalar(select(func.count()).select_from(models.Activo)),
        "primera_fecha": db.scalar(select(func.min(models.Asiento.fecha))),
        "ultima_fecha": db.scalar(select(func.max(models.Asiento.fecha))),
    }
    esquema = {
        **ia_tools.DESCRIPCION_ESQUEMA,
        "endpoints_consulta": ENDPOINTS_CONSULTA,
        "exportacion": EXPORTACION,
    }
    return {"esquema": esquema, "estadisticas": stats}


@router.get("/estado")
def estado():
    """Comprueba si Ollama está disponible y si el modelo configurado está descargado."""
    return ollama_client.estado()


@router.post("/preguntar", response_model=schemas.PreguntarOut)
def preguntar(datos: schemas.PreguntarIn, db: Session = Depends(get_db)):
    """Responde una pregunta en lenguaje natural sobre los datos de la empresa activa."""
    try:
        return svc_asistente.responder(db, datos.pregunta, datos.historial)
    except ollama_client.OllamaNoDisponible as exc:
        raise HTTPException(503, str(exc)) from exc
