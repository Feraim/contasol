from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..money import a_euros
from . import asientos as svc_asientos


def _dias_del_anio(anio: int) -> int:
    return (date(anio + 1, 1, 1) - date(anio, 1, 1)).days


def dotacion_del_ejercicio(activo: models.Activo, ejercicio: int, ya_amortizado: int) -> int:
    """Dotación lineal del ejercicio: prorrateo por días el año de compra,
    resto pendiente en el último ejercicio del plan (absorbe redondeos)."""
    amortizable = activo.valor - activo.valor_residual
    pendiente = amortizable - ya_amortizado
    if pendiente <= 0:
        return 0
    adq = activo.fecha_adquisicion
    comprado_a_1_enero = adq.month == 1 and adq.day == 1
    ultimo_ejercicio = adq.year + activo.vida_util_anios - (1 if comprado_a_1_enero else 0)
    if ejercicio >= ultimo_ejercicio:
        return pendiente
    anual = round(amortizable / activo.vida_util_anios)
    if ejercicio == adq.year:
        dias = (date(ejercicio + 1, 1, 1) - adq).days
        anual = round(anual * dias / _dias_del_anio(ejercicio))
    return min(anual, pendiente)


def amortizar(db: Session, activo_id: int, ejercicio: int) -> models.Amortizacion:
    activo = db.get(models.Activo, activo_id)
    if activo is None:
        raise HTTPException(404, "Activo no encontrado")
    if ejercicio < activo.fecha_adquisicion.year:
        raise HTTPException(422, "El ejercicio es anterior a la adquisición del activo")
    if any(am.ejercicio == ejercicio for am in activo.amortizaciones):
        raise HTTPException(409, f"El ejercicio {ejercicio} ya está dotado para este activo")

    ya_amortizado = sum(am.importe for am in activo.amortizaciones)
    importe = dotacion_del_ejercicio(activo, ejercicio, ya_amortizado)
    if importe <= 0:
        raise HTTPException(409, "El activo ya está totalmente amortizado")

    concepto = f"Amortización {ejercicio} · {activo.nombre}"
    asiento = svc_asientos.crear_asiento_directo(
        db,
        date(ejercicio, 12, 31),
        concepto,
        [
            models.Apunte(cuenta_codigo=activo.cuenta_gasto, debe=importe, concepto=concepto),
            models.Apunte(cuenta_codigo=activo.cuenta_amort_acum, haber=importe, concepto=concepto),
        ],
    )
    dotacion = models.Amortizacion(
        activo_id=activo.id, ejercicio=ejercicio, importe=importe, asiento_id=asiento.id
    )
    db.add(dotacion)
    db.commit()
    return dotacion


def eliminar_dotacion(db: Session, activo_id: int, ejercicio: int) -> None:
    dotacion = db.scalar(
        select(models.Amortizacion).where(
            models.Amortizacion.activo_id == activo_id,
            models.Amortizacion.ejercicio == ejercicio,
        )
    )
    if dotacion is None:
        raise HTTPException(404, "Dotación no encontrada")
    asiento_id = dotacion.asiento_id
    db.delete(dotacion)
    db.flush()
    if asiento_id is not None:
        asiento = db.get(models.Asiento, asiento_id)
        if asiento is not None:
            db.delete(asiento)
    db.commit()


def serializar(activo: models.Activo) -> dict:
    amortizado = sum(am.importe for am in activo.amortizaciones)
    return {
        "id": activo.id,
        "nombre": activo.nombre,
        "fecha_adquisicion": activo.fecha_adquisicion,
        "valor": a_euros(activo.valor),
        "valor_residual": a_euros(activo.valor_residual),
        "vida_util_anios": activo.vida_util_anios,
        "cuenta_activo": activo.cuenta_activo,
        "cuenta_amort_acum": activo.cuenta_amort_acum,
        "cuenta_gasto": activo.cuenta_gasto,
        "amortizado": a_euros(amortizado),
        "valor_neto": a_euros(activo.valor - amortizado),
        "amortizaciones": [
            {"ejercicio": am.ejercicio, "importe": a_euros(am.importe), "asiento_id": am.asiento_id}
            for am in activo.amortizaciones
        ],
    }
