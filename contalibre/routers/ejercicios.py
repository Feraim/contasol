from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import cierre as svc

router = APIRouter(prefix="/ejercicios", tags=["ejercicios"])


@router.get("", response_model=list[schemas.EjercicioOut])
def listar(db: Session = Depends(get_db)):
    return svc.listar(db)


@router.get("/{anio}", response_model=schemas.EjercicioOut)
def detalle(anio: int, db: Session = Depends(get_db)):
    return svc.detalle(db, anio)


@router.post("/{anio}/cerrar", response_model=schemas.EjercicioOut)
def cerrar(anio: int, db: Session = Depends(get_db)):
    ejercicio = svc.cerrar(db, anio)
    return svc.serializar(ejercicio)


@router.post("/{anio}/abrir", response_model=schemas.EjercicioOut)
def abrir(anio: int, db: Session = Depends(get_db)):
    ejercicio = svc.abrir(db, anio)
    return svc.serializar(ejercicio)


@router.delete("/{anio}/cierre", status_code=204)
def deshacer_cierre(anio: int, db: Session = Depends(get_db)):
    svc.deshacer_cierre(db, anio)


@router.delete("/{anio}/apertura", status_code=204)
def deshacer_apertura(anio: int, db: Session = Depends(get_db)):
    svc.deshacer_apertura(db, anio)
