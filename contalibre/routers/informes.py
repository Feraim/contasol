from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_db
from ..services import exportacion as export
from ..services import informes as svc

router = APIRouter(prefix="/informes", tags=["informes"])

_FORMATO = Query("json", pattern="^(json|pdf|excel)$")


@router.get("/panel")
def panel(db: Session = Depends(get_db)):
    return svc.panel(db)


def _tabla_mayor(m: dict) -> tuple[list[str], list[list]]:
    columnas = ["Fecha", "Asiento", "Cuenta", "Concepto", "Debe", "Haber", "Saldo"]
    filas = [
        [x["fecha"], str(x["asiento"]), x["cuenta"], x["concepto"], x["debe"], x["haber"], x["saldo"]]
        for x in m["movimientos"]
    ]
    return columnas, filas


@router.get("/mayor")
def mayor(
    cuenta: str = Query(min_length=1),
    desde: date | None = None,
    hasta: date | None = None,
    formato: str = _FORMATO,
    db: Session = Depends(get_db),
):
    m = svc.mayor(db, cuenta, desde, hasta)
    if formato == "json":
        return m
    columnas, filas = _tabla_mayor(m)
    return export.respuesta(
        formato, f"mayor_{cuenta}", f"Libro mayor · {m['cuenta']} {m['nombre']}", columnas, filas,
        subtitulo=f"Saldo: {export.formatear(m['saldo'])} €",
    )


def _tabla_sumas(s: dict) -> tuple[list[str], list[list]]:
    columnas = ["Cuenta", "Nombre", "Debe", "Haber", "Saldo deudor", "Saldo acreedor"]
    filas = [
        [f["cuenta"], f["nombre"], f["debe"], f["haber"], f["saldo_deudor"], f["saldo_acreedor"]]
        for f in s["filas"]
    ]
    filas.append(["TOTALES", "", s["total_debe"], s["total_haber"], "", ""])
    return columnas, filas


@router.get("/sumas-saldos")
def sumas_saldos(
    desde: date | None = None, hasta: date | None = None, formato: str = _FORMATO,
    db: Session = Depends(get_db),
):
    s = svc.sumas_y_saldos(db, desde, hasta)
    if formato == "json":
        return s
    columnas, filas = _tabla_sumas(s)
    return export.respuesta(
        formato, "sumas_y_saldos", "Balance de sumas y saldos", columnas, filas,
        subtitulo="Cuadrado ✓" if s["cuadrado"] else "⚠ Descuadre",
    )


def _tabla_pyg(p: dict) -> tuple[list[str], list[list]]:
    columnas = ["Bloque", "Cuenta", "Nombre", "Importe"]
    filas = [["Ingresos", f["cuenta"], f["nombre"], f["importe"]] for f in p["ingresos"]]
    filas += [["Gastos", f["cuenta"], f["nombre"], f["importe"]] for f in p["gastos"]]
    filas.append(["Total ingresos", "", "", p["total_ingresos"]])
    filas.append(["Total gastos", "", "", p["total_gastos"]])
    filas.append(["Resultado", "", "", p["resultado"]])
    return columnas, filas


@router.get("/pyg")
def perdidas_ganancias(
    desde: date | None = None, hasta: date | None = None, formato: str = _FORMATO,
    db: Session = Depends(get_db),
):
    p = svc.perdidas_y_ganancias(db, desde, hasta)
    if formato == "json":
        return p
    columnas, filas = _tabla_pyg(p)
    return export.respuesta(
        formato, "perdidas_y_ganancias", "Cuenta de pérdidas y ganancias", columnas, filas,
        subtitulo=f"Resultado: {export.formatear(p['resultado'])} €",
    )


def _tabla_balance(b: dict) -> tuple[list[str], list[list]]:
    columnas = ["Lado", "Sección", "Cuenta", "Nombre", "Importe"]
    filas = []
    for seccion, items in b["activo"].items():
        filas += [["Activo", seccion, f["cuenta"], f["nombre"], f["importe"]] for f in items]
    for seccion, items in b["pasivo"].items():
        filas += [["Patrimonio neto y pasivo", seccion, f["cuenta"], f["nombre"], f["importe"]] for f in items]
    filas.append(["TOTAL ACTIVO", "", "", "", b["total_activo"]])
    filas.append(["TOTAL PATRIMONIO NETO Y PASIVO", "", "", "", b["total_pasivo"]])
    return columnas, filas


@router.get("/balance")
def balance(hasta: date | None = None, formato: str = _FORMATO, db: Session = Depends(get_db)):
    b = svc.balance_situacion(db, hasta)
    if formato == "json":
        return b
    columnas, filas = _tabla_balance(b)
    return export.respuesta(
        formato, "balance_situacion", "Balance de situación", columnas, filas,
        subtitulo="Cuadrado ✓" if b["cuadrado"] else "⚠ Descuadre",
    )


@router.get("/iva")
def iva(
    ejercicio: int = Query(ge=1900, le=2200),
    trimestre: int = Query(ge=1, le=4),
    db: Session = Depends(get_db),
):
    return svc.resumen_iva(db, ejercicio, trimestre)
