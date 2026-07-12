from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_db
from ..services import facturas as svc

router = APIRouter(prefix="/facturas", tags=["facturas"])


@router.get("", response_model=list[schemas.FacturaOut])
def listar(
    tipo: str | None = None,
    estado: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
):
    q = select(models.Factura).order_by(models.Factura.fecha.desc(), models.Factura.id.desc())
    if tipo in ("emitida", "recibida"):
        q = q.where(models.Factura.tipo == tipo)
    if estado in ("pendiente", "pagada"):
        q = q.where(models.Factura.estado == estado)
    if desde:
        q = q.where(models.Factura.fecha >= desde)
    if hasta:
        q = q.where(models.Factura.fecha <= hasta)
    return [svc.serializar(f) for f in db.scalars(q)]


@router.get("/{factura_id}", response_model=schemas.FacturaOut)
def detalle(factura_id: int, db: Session = Depends(get_db)):
    factura = db.get(models.Factura, factura_id)
    if factura is None:
        raise HTTPException(404, "Factura no encontrada")
    return svc.serializar(factura)


@router.post("", response_model=schemas.FacturaOut, status_code=201)
def crear(datos: schemas.FacturaIn, db: Session = Depends(get_db)):
    return svc.serializar(svc.crear_factura(db, datos))


@router.post("/{factura_id}/liquidar", response_model=schemas.FacturaOut)
def liquidar(factura_id: int, datos: schemas.LiquidarIn, db: Session = Depends(get_db)):
    return svc.serializar(svc.liquidar_factura(db, factura_id, datos))


@router.delete("/{factura_id}", status_code=204)
def eliminar(factura_id: int, db: Session = Depends(get_db)):
    svc.eliminar_factura(db, factura_id)
