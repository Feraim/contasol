from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import informes as svc

router = APIRouter(prefix="/informes", tags=["informes"])


@router.get("/panel")
def panel(db: Session = Depends(get_db)):
    return svc.panel(db)


@router.get("/mayor")
def mayor(
    cuenta: str = Query(min_length=1),
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
):
    return svc.mayor(db, cuenta, desde, hasta)


@router.get("/sumas-saldos")
def sumas_saldos(
    desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)
):
    return svc.sumas_y_saldos(db, desde, hasta)


@router.get("/pyg")
def perdidas_ganancias(
    desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)
):
    return svc.perdidas_y_ganancias(db, desde, hasta)


@router.get("/balance")
def balance(hasta: date | None = None, db: Session = Depends(get_db)):
    return svc.balance_situacion(db, hasta)


@router.get("/iva")
def iva(
    ejercicio: int = Query(ge=1900, le=2200),
    trimestre: int = Query(ge=1, le=4),
    db: Session = Depends(get_db),
):
    return svc.resumen_iva(db, ejercicio, trimestre)
