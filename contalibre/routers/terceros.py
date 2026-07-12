from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/terceros", tags=["terceros"])


@router.get("", response_model=list[schemas.TerceroOut])
def listar(q: str | None = None, tipo: str | None = None, db: Session = Depends(get_db)):
    consulta = select(models.Tercero).order_by(models.Tercero.nombre)
    if q:
        consulta = consulta.where(
            models.Tercero.nombre.icontains(q) | models.Tercero.nif.icontains(q)
        )
    if tipo in ("cliente", "proveedor"):
        consulta = consulta.where(models.Tercero.tipo.in_((tipo, "ambos")))
    return db.scalars(consulta).all()


@router.post("", response_model=schemas.TerceroOut, status_code=201)
def crear(datos: schemas.TerceroIn, db: Session = Depends(get_db)):
    existente = db.scalar(select(models.Tercero).where(models.Tercero.nif == datos.nif))
    if existente is not None:
        raise HTTPException(409, f"Ya existe un tercero con NIF {datos.nif}")
    tercero = models.Tercero(**datos.model_dump())
    db.add(tercero)
    db.commit()
    return tercero


@router.put("/{tercero_id}", response_model=schemas.TerceroOut)
def actualizar(tercero_id: int, datos: schemas.TerceroIn, db: Session = Depends(get_db)):
    tercero = db.get(models.Tercero, tercero_id)
    if tercero is None:
        raise HTTPException(404, "Tercero no encontrado")
    duplicado = db.scalar(
        select(models.Tercero).where(
            models.Tercero.nif == datos.nif, models.Tercero.id != tercero_id
        )
    )
    if duplicado is not None:
        raise HTTPException(409, f"Ya existe otro tercero con NIF {datos.nif}")
    for campo, valor in datos.model_dump().items():
        setattr(tercero, campo, valor)
    db.commit()
    return tercero


@router.delete("/{tercero_id}", status_code=204)
def eliminar(tercero_id: int, db: Session = Depends(get_db)):
    tercero = db.get(models.Tercero, tercero_id)
    if tercero is None:
        raise HTTPException(404, "Tercero no encontrado")
    con_facturas = db.scalar(
        select(models.Factura.id).where(models.Factura.tercero_id == tercero_id).limit(1)
    )
    if con_facturas is not None:
        raise HTTPException(409, "El tercero tiene facturas y no puede eliminarse")
    db.delete(tercero)
    db.commit()
