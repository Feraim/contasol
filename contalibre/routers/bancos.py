from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..deps import get_db
from ..services import conciliacion as svc

router = APIRouter(prefix="/bancos", tags=["bancos"])


@router.post("/importar", response_model=list[schemas.MovimientoBancarioOut], status_code=201)
def importar(datos: schemas.ImportarNorma43In, db: Session = Depends(get_db)):
    movimientos = svc.importar(db, datos.cuenta_tesoreria, datos.contenido)
    return [svc.serializar(m) for m in movimientos]


@router.get("/movimientos", response_model=list[schemas.MovimientoBancarioOut])
def movimientos(
    cuenta: str | None = None,
    conciliado: bool | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
):
    return [svc.serializar(m) for m in svc.listar(db, cuenta, conciliado, desde, hasta)]


@router.post("/{movimiento_id}/conciliar", response_model=schemas.MovimientoBancarioOut)
def conciliar(movimiento_id: int, datos: schemas.ConciliarIn, db: Session = Depends(get_db)):
    m = svc.conciliar_manual(db, movimiento_id, datos.apunte_id)
    return svc.serializar(m)


@router.post("/{movimiento_id}/conciliar-nuevo", response_model=schemas.MovimientoBancarioOut)
def conciliar_nuevo(movimiento_id: int, datos: schemas.ConciliarNuevoIn, db: Session = Depends(get_db)):
    m = svc.conciliar_creando_asiento(db, movimiento_id, datos.cuenta_contrapartida, datos.concepto)
    return svc.serializar(m)


@router.delete("/{movimiento_id}/conciliacion", response_model=schemas.MovimientoBancarioOut)
def deshacer_conciliacion(movimiento_id: int, db: Session = Depends(get_db)):
    m = svc.desconciliar(db, movimiento_id)
    return svc.serializar(m)


@router.delete("/{movimiento_id}", status_code=204)
def eliminar(movimiento_id: int, db: Session = Depends(get_db)):
    svc.eliminar(db, movimiento_id)
