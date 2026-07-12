from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import asientos as svc

router = APIRouter(prefix="/asientos", tags=["asientos"])


@router.get("", response_model=list[schemas.AsientoOut])
def listar(
    desde: date | None = None,
    hasta: date | None = None,
    cuenta: str | None = None,
    limite: int = 200,
    db: Session = Depends(get_db),
):
    q = select(models.Asiento).order_by(
        models.Asiento.fecha.desc(), models.Asiento.numero.desc()
    )
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)
    if cuenta:
        q = q.join(models.Apunte).where(models.Apunte.cuenta_codigo.startswith(cuenta)).distinct()
    q = q.limit(min(limite, 1000))
    return [svc.serializar(db, a) for a in db.scalars(q).unique()]


@router.get("/{asiento_id}", response_model=schemas.AsientoOut)
def detalle(asiento_id: int, db: Session = Depends(get_db)):
    asiento = db.get(models.Asiento, asiento_id)
    if asiento is None:
        raise HTTPException(404, "Asiento no encontrado")
    return svc.serializar(db, asiento)


@router.post("", response_model=schemas.AsientoOut, status_code=201)
def crear(datos: schemas.AsientoIn, db: Session = Depends(get_db)):
    asiento = svc.crear_asiento(db, datos)
    db.commit()
    return svc.serializar(db, asiento)


@router.delete("/{asiento_id}", status_code=204)
def eliminar(asiento_id: int, db: Session = Depends(get_db)):
    svc.eliminar_asiento(db, asiento_id)
