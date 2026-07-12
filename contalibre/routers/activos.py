from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..money import a_centimos
from ..services import amortizacion as svc
from ..services import asientos as svc_asientos

router = APIRouter(prefix="/activos", tags=["inmovilizado"])


@router.get("", response_model=list[schemas.ActivoOut])
def listar(db: Session = Depends(get_db)):
    return [svc.serializar(a) for a in db.scalars(select(models.Activo).order_by(models.Activo.id))]


@router.get("/{activo_id}", response_model=schemas.ActivoOut)
def detalle(activo_id: int, db: Session = Depends(get_db)):
    activo = db.get(models.Activo, activo_id)
    if activo is None:
        raise HTTPException(404, "Activo no encontrado")
    return svc.serializar(activo)


@router.post("", response_model=schemas.ActivoOut, status_code=201)
def crear(datos: schemas.ActivoIn, db: Session = Depends(get_db)):
    valor = a_centimos(datos.valor)
    residual = a_centimos(datos.valor_residual)
    if residual >= valor:
        raise HTTPException(422, "El valor residual debe ser menor que el valor del activo")
    svc_asientos.validar_cuentas(
        db, {datos.cuenta_activo, datos.cuenta_amort_acum, datos.cuenta_gasto}
    )
    activo = models.Activo(
        nombre=datos.nombre,
        fecha_adquisicion=datos.fecha_adquisicion,
        valor=valor,
        valor_residual=residual,
        vida_util_anios=datos.vida_util_anios,
        cuenta_activo=datos.cuenta_activo,
        cuenta_amort_acum=datos.cuenta_amort_acum,
        cuenta_gasto=datos.cuenta_gasto,
    )
    db.add(activo)
    db.commit()
    return svc.serializar(activo)


@router.post("/{activo_id}/amortizar", response_model=schemas.ActivoOut)
def amortizar(activo_id: int, datos: schemas.AmortizarIn, db: Session = Depends(get_db)):
    svc.amortizar(db, activo_id, datos.ejercicio)
    return svc.serializar(db.get(models.Activo, activo_id))


@router.delete("/{activo_id}/amortizaciones/{ejercicio}", status_code=204)
def eliminar_dotacion(activo_id: int, ejercicio: int, db: Session = Depends(get_db)):
    svc.eliminar_dotacion(db, activo_id, ejercicio)


@router.delete("/{activo_id}", status_code=204)
def eliminar(activo_id: int, db: Session = Depends(get_db)):
    activo = db.get(models.Activo, activo_id)
    if activo is None:
        raise HTTPException(404, "Activo no encontrado")
    if activo.amortizaciones:
        raise HTTPException(
            409, "El activo tiene dotaciones de amortización; elimínalas primero"
        )
    db.delete(activo)
    db.commit()
