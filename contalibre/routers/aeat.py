from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import aeat as svc
from ..services import exportacion as export

router = APIRouter(prefix="/aeat", tags=["aeat"])

_FORMATO = Query("json", pattern="^(json|pdf|excel)$")


def _tabla_303(m: dict) -> tuple[list[str], list[list]]:
    columnas = ["Concepto", "Base", "Tipo %", "Cuota"]
    filas = [
        [f"IVA devengado {f['tipo_iva']:.0f}%", f["base"], f["tipo_iva"], f["cuota"]]
        for f in m["iva_devengado"]["desglose"]
    ]
    filas.append(
        ["Casilla 27 · Total cuota devengada", "", "", m["iva_devengado"]["casilla_27_cuota_devengada"]]
    )
    filas.append(
        ["Casilla 28/29 · Base y cuota deducible", m["iva_deducible"]["casilla_28_base"], "",
         m["iva_deducible"]["casilla_29_cuota"]]
    )
    filas.append(["Casilla 44 · Total a deducir", "", "", m["iva_deducible"]["casilla_44_total_a_deducir"]])
    filas.append(["Casilla 46/69 · Resultado de la liquidación", "", "", m["casilla_69_resultado_liquidacion"]])
    return columnas, filas


def _tabla_390(m: dict) -> tuple[list[str], list[list]]:
    columnas = ["Bloque", "Tipo %", "Base", "Cuota"]
    filas = [["IVA devengado", f["tipo_iva"], f["base"], f["cuota"]] for f in m["iva_devengado"]]
    filas += [["IVA deducible", f["tipo_iva"], f["base"], f["cuota"]] for f in m["iva_deducible"]]
    filas.append(["Total devengado", "", "", m["total_devengado"]])
    filas.append(["Total deducible", "", "", m["total_deducible"]])
    filas.append(["Resultado anual", "", "", m["resultado_anual"]])
    for r in m["resultados_trimestrales"]:
        filas.append([f"Resultado {r['trimestre']}T", "", "", f"{r['resultado']} ({r['sentido']})"])
    return columnas, filas


def _tabla_347(m: dict) -> tuple[list[str], list[list]]:
    columnas = ["NIF", "Nombre", "Operación", "Importe anual", "1T", "2T", "3T", "4T"]
    filas = [
        [
            r["nif"], r["nombre"], r["operacion"], r["importe_anual"],
            r["trimestres"]["1"], r["trimestres"]["2"], r["trimestres"]["3"], r["trimestres"]["4"],
        ]
        for r in m["registros"]
    ]
    return columnas, filas


@router.get("/303")
def modelo_303(
    ejercicio: int = Query(ge=1900, le=2200),
    trimestre: int = Query(ge=1, le=4),
    formato: str = _FORMATO,
    db: Session = Depends(get_db),
):
    m = svc.modelo_303(db, ejercicio, trimestre)
    if formato == "json":
        return m
    columnas, filas = _tabla_303(m)
    resultado = export.formatear(m["casilla_69_resultado_liquidacion"])
    return export.respuesta(
        formato, f"modelo303_{ejercicio}_{trimestre}T", f"Modelo 303 · {trimestre}T {ejercicio}",
        columnas, filas, subtitulo=f"Resultado de la liquidación: {resultado} € ({m['sentido']})",
    )


@router.get("/390")
def modelo_390(
    ejercicio: int = Query(ge=1900, le=2200),
    formato: str = _FORMATO,
    db: Session = Depends(get_db),
):
    m = svc.modelo_390(db, ejercicio)
    if formato == "json":
        return m
    columnas, filas = _tabla_390(m)
    return export.respuesta(
        formato, f"modelo390_{ejercicio}", f"Modelo 390 · Resumen anual de IVA {ejercicio}",
        columnas, filas, subtitulo=f"Resultado anual informativo: {export.formatear(m['resultado_anual'])} €",
    )


@router.get("/347")
def modelo_347(
    ejercicio: int = Query(ge=1900, le=2200),
    formato: str = _FORMATO,
    db: Session = Depends(get_db),
):
    m = svc.modelo_347(db, ejercicio)
    if formato == "json":
        return m
    columnas, filas = _tabla_347(m)
    subtitulo = f"Umbral: {export.formatear(m['umbral'])} € · Total declarado: {export.formatear(m['total_declarado'])} €"
    return export.respuesta(
        formato, f"modelo347_{ejercicio}", f"Modelo 347 · Operaciones con terceros {ejercicio}",
        columnas, filas, subtitulo=subtitulo,
    )
