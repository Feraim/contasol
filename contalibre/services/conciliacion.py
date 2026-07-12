from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..money import a_euros
from . import asientos as svc_asientos
from . import norma43


def _duplicado(db: Session, cuenta: str, mov: norma43.MovimientoN43) -> bool:
    return (
        db.scalar(
            select(models.MovimientoBancario.id).where(
                models.MovimientoBancario.cuenta_tesoreria == cuenta,
                models.MovimientoBancario.fecha_operacion == mov.fecha_operacion,
                models.MovimientoBancario.importe == mov.importe,
                models.MovimientoBancario.documento == mov.documento,
                models.MovimientoBancario.referencia == f"{mov.referencia1} {mov.referencia2}".strip(),
            )
        )
        is not None
    )


def _apunte_libre_candidato(db: Session, cuenta: str, importe: int, fecha: date) -> models.Apunte | None:
    usados = select(models.MovimientoBancario.apunte_id).where(
        models.MovimientoBancario.apunte_id.is_not(None)
    )
    candidatos = db.scalars(
        select(models.Apunte)
        .join(models.Asiento)
        .where(
            models.Apunte.cuenta_codigo == cuenta,
            (models.Apunte.debe - models.Apunte.haber) == importe,
            models.Asiento.fecha == fecha,
            models.Apunte.id.not_in(usados),
        )
    ).all()
    return candidatos[0] if len(candidatos) == 1 else None


def importar(db: Session, cuenta_tesoreria: str, contenido: str) -> list[models.MovimientoBancario]:
    svc_asientos.validar_cuentas(db, {cuenta_tesoreria})
    movimientos = norma43.parsear(contenido)

    creados: list[models.MovimientoBancario] = []
    for mov in movimientos:
        if _duplicado(db, cuenta_tesoreria, mov):
            continue
        fila = models.MovimientoBancario(
            cuenta_tesoreria=cuenta_tesoreria,
            fecha_operacion=mov.fecha_operacion,
            fecha_valor=mov.fecha_valor,
            concepto=mov.concepto,
            importe=mov.importe,
            documento=mov.documento,
            referencia=f"{mov.referencia1} {mov.referencia2}".strip(),
        )
        db.add(fila)
        db.flush()
        candidato = _apunte_libre_candidato(db, cuenta_tesoreria, mov.importe, mov.fecha_operacion)
        if candidato is not None:
            fila.apunte_id = candidato.id
            fila.conciliado = True
        creados.append(fila)
    db.commit()
    return creados


def listar(
    db: Session,
    cuenta: str | None = None,
    conciliado: bool | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> list[models.MovimientoBancario]:
    q = select(models.MovimientoBancario).order_by(
        models.MovimientoBancario.fecha_operacion.desc(), models.MovimientoBancario.id.desc()
    )
    if cuenta:
        q = q.where(models.MovimientoBancario.cuenta_tesoreria == cuenta)
    if conciliado is not None:
        q = q.where(models.MovimientoBancario.conciliado == conciliado)
    if desde:
        q = q.where(models.MovimientoBancario.fecha_operacion >= desde)
    if hasta:
        q = q.where(models.MovimientoBancario.fecha_operacion <= hasta)
    return list(db.scalars(q))


def conciliar_manual(db: Session, movimiento_id: int, apunte_id: int) -> models.MovimientoBancario:
    movimiento = db.get(models.MovimientoBancario, movimiento_id)
    if movimiento is None:
        raise HTTPException(404, "Movimiento bancario no encontrado")
    if movimiento.conciliado:
        raise HTTPException(409, "El movimiento ya está conciliado")
    apunte = db.get(models.Apunte, apunte_id)
    if apunte is None:
        raise HTTPException(404, "Apunte no encontrado")
    if apunte.cuenta_codigo != movimiento.cuenta_tesoreria:
        raise HTTPException(422, "El apunte no pertenece a la cuenta de tesorería del movimiento")
    if (apunte.debe - apunte.haber) != movimiento.importe:
        raise HTTPException(422, "El importe del apunte no coincide con el del movimiento")
    ya_usado = db.scalar(
        select(models.MovimientoBancario.id).where(models.MovimientoBancario.apunte_id == apunte.id)
    )
    if ya_usado is not None:
        raise HTTPException(409, "Ese apunte ya está conciliado con otro movimiento")
    movimiento.apunte_id = apunte.id
    movimiento.conciliado = True
    db.commit()
    return movimiento


def conciliar_creando_asiento(
    db: Session, movimiento_id: int, cuenta_contrapartida: str, concepto: str = ""
) -> models.MovimientoBancario:
    movimiento = db.get(models.MovimientoBancario, movimiento_id)
    if movimiento is None:
        raise HTTPException(404, "Movimiento bancario no encontrado")
    if movimiento.conciliado:
        raise HTTPException(409, "El movimiento ya está conciliado")
    svc_asientos.validar_cuentas(db, {cuenta_contrapartida})

    texto = concepto or movimiento.concepto or "Movimiento bancario conciliado"
    importe = abs(movimiento.importe)
    if movimiento.importe > 0:
        apuntes = [
            models.Apunte(cuenta_codigo=movimiento.cuenta_tesoreria, debe=importe, concepto=texto),
            models.Apunte(cuenta_codigo=cuenta_contrapartida, haber=importe, concepto=texto),
        ]
    else:
        apuntes = [
            models.Apunte(cuenta_codigo=movimiento.cuenta_tesoreria, haber=importe, concepto=texto),
            models.Apunte(cuenta_codigo=cuenta_contrapartida, debe=importe, concepto=texto),
        ]
    asiento = svc_asientos.crear_asiento_directo(db, movimiento.fecha_operacion, texto, apuntes)
    apunte_tesoreria = next(a for a in asiento.apuntes if a.cuenta_codigo == movimiento.cuenta_tesoreria)
    movimiento.apunte_id = apunte_tesoreria.id
    movimiento.conciliado = True
    db.commit()
    return movimiento


def desconciliar(db: Session, movimiento_id: int) -> models.MovimientoBancario:
    movimiento = db.get(models.MovimientoBancario, movimiento_id)
    if movimiento is None:
        raise HTTPException(404, "Movimiento bancario no encontrado")
    if not movimiento.conciliado:
        raise HTTPException(409, "El movimiento no está conciliado")
    movimiento.apunte_id = None
    movimiento.conciliado = False
    db.commit()
    return movimiento


def eliminar(db: Session, movimiento_id: int) -> None:
    movimiento = db.get(models.MovimientoBancario, movimiento_id)
    if movimiento is None:
        raise HTTPException(404, "Movimiento bancario no encontrado")
    if movimiento.conciliado:
        raise HTTPException(409, "Desconcilia el movimiento antes de eliminarlo")
    db.delete(movimiento)
    db.commit()


def serializar(m: models.MovimientoBancario) -> dict:
    return {
        "id": m.id,
        "cuenta_tesoreria": m.cuenta_tesoreria,
        "fecha_operacion": m.fecha_operacion,
        "fecha_valor": m.fecha_valor,
        "concepto": m.concepto,
        "importe": a_euros(m.importe),
        "documento": m.documento,
        "referencia": m.referencia,
        "conciliado": m.conciliado,
        "apunte_id": m.apunte_id,
    }
