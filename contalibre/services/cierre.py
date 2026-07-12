from datetime import date

from fastapi import HTTPException
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from .. import models
from ..money import a_euros
from . import asientos as svc_asientos
from .informes import _saldos

CUENTA_RESULTADO = "129"


def _primer_anio_con_movimientos(db: Session) -> int | None:
    fecha = db.scalar(select(func.min(models.Asiento.fecha)))
    return fecha.year if fecha else None


def _resultado_periodo(db: Session, desde: date, hasta: date) -> int:
    """Ingresos menos gastos (céntimos) de las cuentas de gestión (6 y 7) en el rango."""
    saldos = _saldos(db, desde, hasta)
    return sum(
        (haber - debe) if codigo.startswith("7") else -(debe - haber)
        for codigo, (debe, haber) in saldos.items()
        if codigo.startswith(("6", "7"))
    )


def _regularizar_pyg(db: Session, anio: int) -> tuple[models.Asiento | None, int]:
    """Salda las cuentas de gestión (6 y 7) del ejercicio contra la 129."""
    saldos = _saldos(db, date(anio, 1, 1), date(anio, 12, 31))
    concepto = f"Regularización de pérdidas y ganancias {anio}"
    apuntes = []
    resultado = 0
    for codigo, (debe, haber) in sorted(saldos.items()):
        if not codigo.startswith(("6", "7")):
            continue
        saldo = debe - haber
        if saldo == 0:
            continue
        resultado -= saldo
        if saldo > 0:
            apuntes.append(models.Apunte(cuenta_codigo=codigo, haber=saldo, concepto=concepto))
        else:
            apuntes.append(models.Apunte(cuenta_codigo=codigo, debe=-saldo, concepto=concepto))
    if not apuntes:
        return None, 0
    if resultado > 0:
        apuntes.append(
            models.Apunte(cuenta_codigo=CUENTA_RESULTADO, haber=resultado, concepto=concepto)
        )
    elif resultado < 0:
        apuntes.append(
            models.Apunte(cuenta_codigo=CUENTA_RESULTADO, debe=-resultado, concepto=concepto)
        )
    asiento = svc_asientos.crear_asiento_directo(db, date(anio, 12, 31), concepto, apuntes)
    return asiento, resultado


def _cerrar_balance(db: Session, anio: int) -> models.Asiento | None:
    """Salda a cero todas las cuentas patrimoniales (grupos 1-5), ya regularizadas
    las de gestión, mediante el asiento de cierre del ejercicio."""
    saldos = _saldos(db, None, date(anio, 12, 31))
    concepto = f"Cierre del ejercicio {anio}"
    apuntes = []
    for codigo, (debe, haber) in sorted(saldos.items()):
        if codigo.startswith(("6", "7")):
            continue
        saldo = debe - haber
        if saldo == 0:
            continue
        if saldo > 0:
            apuntes.append(models.Apunte(cuenta_codigo=codigo, haber=saldo, concepto=concepto))
        else:
            apuntes.append(models.Apunte(cuenta_codigo=codigo, debe=-saldo, concepto=concepto))
    if not apuntes:
        return None
    return svc_asientos.crear_asiento_directo(db, date(anio, 12, 31), concepto, apuntes)


def cerrar(db: Session, anio: int) -> models.Ejercicio:
    ejercicio = db.get(models.Ejercicio, anio)
    if ejercicio is not None and ejercicio.cerrado:
        raise HTTPException(409, f"El ejercicio {anio} ya está cerrado")

    primer_anio = _primer_anio_con_movimientos(db)
    if primer_anio is not None and anio > primer_anio:
        anterior = db.get(models.Ejercicio, anio - 1)
        if anterior is None or not anterior.cerrado:
            raise HTTPException(409, f"Debes cerrar antes el ejercicio {anio - 1}")
        if ejercicio is None or not ejercicio.abierto:
            raise HTTPException(409, f"Debes abrir antes el ejercicio {anio}")

    asiento_reg, resultado = _regularizar_pyg(db, anio)
    asiento_cierre = _cerrar_balance(db, anio)

    if ejercicio is None:
        ejercicio = models.Ejercicio(anio=anio)
        db.add(ejercicio)
    ejercicio.cerrado = True
    ejercicio.fecha_cierre = date(anio, 12, 31)
    ejercicio.resultado = resultado
    ejercicio.asiento_regularizacion_id = asiento_reg.id if asiento_reg else None
    ejercicio.asiento_cierre_id = asiento_cierre.id if asiento_cierre else None
    db.commit()
    db.refresh(ejercicio)
    return ejercicio


def abrir(db: Session, anio: int) -> models.Ejercicio:
    ejercicio = db.get(models.Ejercicio, anio)
    if ejercicio is not None and ejercicio.abierto:
        raise HTTPException(409, f"El ejercicio {anio} ya está abierto")

    anterior = db.get(models.Ejercicio, anio - 1)
    if anterior is None or not anterior.cerrado:
        raise HTTPException(
            409,
            f"Debes cerrar antes el ejercicio {anio - 1} (el primer ejercicio no necesita apertura)",
        )

    concepto = f"Apertura del ejercicio {anio}"
    asiento_apertura = None
    if anterior.asiento_cierre_id is not None:
        cierre = db.get(models.Asiento, anterior.asiento_cierre_id)
        apuntes = [
            models.Apunte(
                cuenta_codigo=a.cuenta_codigo, debe=a.haber, haber=a.debe, concepto=concepto
            )
            for a in cierre.apuntes
        ]
        asiento_apertura = svc_asientos.crear_asiento_directo(
            db, date(anio, 1, 1), concepto, apuntes
        )

    if ejercicio is None:
        ejercicio = models.Ejercicio(anio=anio)
        db.add(ejercicio)
    ejercicio.abierto = True
    ejercicio.fecha_apertura = date(anio, 1, 1)
    ejercicio.asiento_apertura_id = asiento_apertura.id if asiento_apertura else None
    db.commit()
    db.refresh(ejercicio)
    return ejercicio


def deshacer_cierre(db: Session, anio: int) -> None:
    ejercicio = db.get(models.Ejercicio, anio)
    if ejercicio is None or not ejercicio.cerrado:
        raise HTTPException(404, f"El ejercicio {anio} no está cerrado")
    siguiente = db.get(models.Ejercicio, anio + 1)
    if siguiente is not None and siguiente.abierto:
        raise HTTPException(
            409, f"No se puede deshacer: el ejercicio {anio + 1} ya está abierto"
        )
    for asiento_id in (ejercicio.asiento_cierre_id, ejercicio.asiento_regularizacion_id):
        if asiento_id is not None:
            asiento = db.get(models.Asiento, asiento_id)
            if asiento is not None:
                db.delete(asiento)
    ejercicio.cerrado = False
    ejercicio.fecha_cierre = None
    ejercicio.resultado = None
    ejercicio.asiento_cierre_id = None
    ejercicio.asiento_regularizacion_id = None
    db.commit()


def deshacer_apertura(db: Session, anio: int) -> None:
    ejercicio = db.get(models.Ejercicio, anio)
    if ejercicio is None or not ejercicio.abierto:
        raise HTTPException(404, f"El ejercicio {anio} no está abierto")
    if ejercicio.cerrado:
        raise HTTPException(409, f"Deshaz antes el cierre del ejercicio {anio}")
    if ejercicio.asiento_apertura_id is not None:
        asiento = db.get(models.Asiento, ejercicio.asiento_apertura_id)
        if asiento is not None:
            db.delete(asiento)
    ejercicio.abierto = False
    ejercicio.fecha_apertura = None
    ejercicio.asiento_apertura_id = None
    db.commit()


def serializar(ejercicio: models.Ejercicio) -> dict:
    return {
        "anio": ejercicio.anio,
        "abierto": ejercicio.abierto,
        "cerrado": ejercicio.cerrado,
        "fecha_apertura": ejercicio.fecha_apertura,
        "fecha_cierre": ejercicio.fecha_cierre,
        "resultado": a_euros(ejercicio.resultado) if ejercicio.resultado is not None else None,
        "asiento_apertura_id": ejercicio.asiento_apertura_id,
        "asiento_regularizacion_id": ejercicio.asiento_regularizacion_id,
        "asiento_cierre_id": ejercicio.asiento_cierre_id,
    }


def listar(db: Session) -> list[dict]:
    anios = {
        int(a)
        for a in db.scalars(
            select(extract("year", models.Asiento.fecha)).distinct()
        )
    }
    ejercicios = {e.anio: e for e in db.scalars(select(models.Ejercicio))}
    anios |= set(ejercicios)
    resultado = []
    for anio in sorted(anios):
        ejercicio = ejercicios.get(anio) or _ejercicio_virtual(anio)
        resultado.append(_serializar_con_previsto(db, ejercicio))
    return resultado


def _ejercicio_virtual(anio: int) -> models.Ejercicio:
    return models.Ejercicio(anio=anio, abierto=False, cerrado=False)


def _serializar_con_previsto(db: Session, ejercicio: models.Ejercicio) -> dict:
    datos = serializar(ejercicio)
    if not ejercicio.cerrado:
        datos["resultado_previsto"] = a_euros(
            _resultado_periodo(db, date(ejercicio.anio, 1, 1), date(ejercicio.anio, 12, 31))
        )
    return datos


def detalle(db: Session, anio: int) -> dict:
    ejercicio = db.get(models.Ejercicio, anio) or _ejercicio_virtual(anio)
    return _serializar_con_previsto(db, ejercicio)
