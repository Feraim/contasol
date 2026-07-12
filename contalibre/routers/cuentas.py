from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/cuentas", tags=["cuentas"])


@router.get("", response_model=list[schemas.CuentaOut])
def listar(q: str | None = None, db: Session = Depends(get_db)):
    consulta = select(models.Cuenta).order_by(models.Cuenta.codigo)
    if q:
        consulta = consulta.where(
            models.Cuenta.codigo.startswith(q) | models.Cuenta.nombre.icontains(q)
        )
    return db.scalars(consulta).all()


@router.post("", response_model=schemas.CuentaOut, status_code=201)
def crear(datos: schemas.CuentaIn, db: Session = Depends(get_db)):
    if db.get(models.Cuenta, datos.codigo) is not None:
        raise HTTPException(409, f"La cuenta {datos.codigo} ya existe")
    cuenta = models.Cuenta(codigo=datos.codigo, nombre=datos.nombre)
    db.add(cuenta)
    db.commit()
    return cuenta


@router.put("/{codigo}", response_model=schemas.CuentaOut)
def renombrar(codigo: str, datos: schemas.CuentaIn, db: Session = Depends(get_db)):
    cuenta = db.get(models.Cuenta, codigo)
    if cuenta is None:
        raise HTTPException(404, "Cuenta no encontrada")
    if datos.codigo != codigo:
        raise HTTPException(422, "El código de una cuenta no se puede cambiar")
    cuenta.nombre = datos.nombre
    db.commit()
    return cuenta


@router.delete("/{codigo}", status_code=204)
def eliminar(codigo: str, db: Session = Depends(get_db)):
    cuenta = db.get(models.Cuenta, codigo)
    if cuenta is None:
        raise HTTPException(404, "Cuenta no encontrada")
    usada = db.scalar(
        select(models.Apunte.id).where(models.Apunte.cuenta_codigo == codigo).limit(1)
    )
    if usada is not None:
        raise HTTPException(409, "La cuenta tiene movimientos y no puede eliminarse")
    db.delete(cuenta)
    db.commit()
