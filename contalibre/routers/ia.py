"""Punto de integración para un modelo de IA local.

La idea: un LLM que corra en la máquina del usuario (Ollama, llama.cpp,
Claude vía API, etc.) recibe el contexto de `GET /api/v1/ia/contexto` como
system prompt y, a partir de ahí, consulta los datos llamando a los
endpoints REST de esta misma API. Aquí no se implementa el modelo; solo se
expone todo lo que necesitará.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/ia", tags=["ia"])

DESCRIPCION_ESQUEMA = {
    "software": "ContaLibre: contabilidad española (PGC) de código abierto",
    "convenciones": {
        "importes": "euros con 2 decimales en la API; céntimos enteros en la base de datos",
        "cuentas": "códigos numéricos del PGC; subcuentas de clientes 430xxxx y de proveedores 400xxxx",
        "partida_doble": "todo asiento cumple suma(debe) == suma(haber)",
    },
    "entidades": {
        "cuentas": "plan contable: codigo, nombre",
        "asientos": "asiento del diario: numero (por ejercicio), fecha, concepto, apuntes[]",
        "apuntes": "línea de asiento: cuenta, concepto, debe, haber",
        "terceros": "clientes/proveedores: nif, nombre, subcuentas contables",
        "facturas": "emitidas/recibidas con líneas (base, tipo_iva, cuota), retención, estado y asiento vinculado",
        "activos": "inmovilizado con plan de amortización lineal y dotaciones por ejercicio",
        "ejercicios": "estado de cierre/apertura por año: regularización 6/7 contra 129 y cierre de balance",
    },
    "endpoints_consulta": {
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
        "GET /openapi.json": "especificación OpenAPI completa",
    },
}


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
    return {"esquema": DESCRIPCION_ESQUEMA, "estadisticas": stats}
