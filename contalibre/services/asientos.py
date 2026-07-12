from datetime import date

from fastapi import HTTPException
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..money import a_centimos, a_euros


def siguiente_numero(db: Session, fecha: date) -> int:
    """Numeración secuencial de asientos dentro del ejercicio (año natural)."""
    maximo = db.scalar(
        select(func.max(models.Asiento.numero)).where(
            extract("year", models.Asiento.fecha) == fecha.year
        )
    )
    return (maximo or 0) + 1


def validar_cuentas(db: Session, codigos: set[str]) -> None:
    existentes = set(
        db.scalars(select(models.Cuenta.codigo).where(models.Cuenta.codigo.in_(codigos)))
    )
    faltan = codigos - existentes
    if faltan:
        raise HTTPException(422, f"Cuentas inexistentes: {', '.join(sorted(faltan))}")


def validar_ejercicio_abierto(db: Session, anio: int) -> None:
    ejercicio = db.get(models.Ejercicio, anio)
    if ejercicio is not None and ejercicio.cerrado:
        raise HTTPException(409, f"El ejercicio {anio} está cerrado; no admite nuevos asientos")


def crear_asiento(db: Session, datos: schemas.AsientoIn) -> models.Asiento:
    apuntes = [
        models.Apunte(
            cuenta_codigo=a.cuenta,
            concepto=a.concepto or datos.concepto,
            debe=a_centimos(a.debe),
            haber=a_centimos(a.haber),
        )
        for a in datos.apuntes
    ]
    return crear_asiento_directo(db, datos.fecha, datos.concepto, apuntes)


def crear_asiento_directo(
    db: Session, fecha: date, concepto: str, apuntes: list[models.Apunte]
) -> models.Asiento:
    """Crea un asiento ya en céntimos, validando la partida doble. No hace commit."""
    for a in apuntes:
        a.debe = a.debe or 0
        a.haber = a.haber or 0
    total_debe = sum(a.debe for a in apuntes)
    total_haber = sum(a.haber for a in apuntes)
    if total_debe != total_haber:
        raise HTTPException(
            422,
            "Asiento descuadrado: debe "
            f"{a_euros(total_debe):.2f} ≠ haber {a_euros(total_haber):.2f}",
        )
    if total_debe == 0:
        raise HTTPException(422, "El asiento no puede tener importe cero")
    for a in apuntes:
        if a.debe < 0 or a.haber < 0:
            raise HTTPException(422, "Los importes no pueden ser negativos")
        if a.debe and a.haber:
            raise HTTPException(422, "Un apunte no puede tener debe y haber a la vez")
    validar_cuentas(db, {a.cuenta_codigo for a in apuntes})
    validar_ejercicio_abierto(db, fecha.year)

    asiento = models.Asiento(
        numero=siguiente_numero(db, fecha), fecha=fecha, concepto=concepto, apuntes=apuntes
    )
    db.add(asiento)
    db.flush()
    return asiento


def asiento_de_factura(db: Session, asiento_id: int) -> models.Factura | None:
    return db.scalar(
        select(models.Factura).where(
            (models.Factura.asiento_id == asiento_id)
            | (models.Factura.asiento_pago_id == asiento_id)
        )
    )


def eliminar_asiento(db: Session, asiento_id: int) -> None:
    asiento = db.get(models.Asiento, asiento_id)
    if asiento is None:
        raise HTTPException(404, "Asiento no encontrado")
    validar_ejercicio_abierto(db, asiento.fecha.year)
    factura = asiento_de_factura(db, asiento_id)
    if factura is not None:
        raise HTTPException(
            409,
            f"El asiento pertenece a la factura {factura.tipo} {factura.numero}; "
            "elimina o modifica la factura en su lugar",
        )
    amortizacion = db.scalar(
        select(models.Amortizacion).where(models.Amortizacion.asiento_id == asiento_id)
    )
    if amortizacion is not None:
        raise HTTPException(
            409,
            "El asiento pertenece a una dotación de amortización; elimínala desde el activo",
        )
    db.delete(asiento)
    db.commit()


def serializar(db: Session, asiento: models.Asiento) -> dict:
    nombres = {
        c.codigo: c.nombre
        for c in db.scalars(
            select(models.Cuenta).where(
                models.Cuenta.codigo.in_({a.cuenta_codigo for a in asiento.apuntes})
            )
        )
    }
    return {
        "id": asiento.id,
        "numero": asiento.numero,
        "fecha": asiento.fecha,
        "concepto": asiento.concepto,
        "apuntes": [
            {
                "id": a.id,
                "cuenta": a.cuenta_codigo,
                "cuenta_nombre": nombres.get(a.cuenta_codigo, ""),
                "concepto": a.concepto,
                "debe": a_euros(a.debe),
                "haber": a_euros(a.haber),
            }
            for a in asiento.apuntes
        ],
    }
