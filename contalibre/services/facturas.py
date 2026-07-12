from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..money import a_centimos, a_euros
from . import asientos as svc_asientos

CUENTA_IVA_REPERCUTIDO = "477"
CUENTA_IVA_SOPORTADO = "472"
CUENTA_RETENCION_SOPORTADA = "473"   # retención que nos practican (emitidas)
CUENTA_RETENCION_PRACTICADA = "4751"  # retención que practicamos (recibidas)


def _pct_a_basis(pct) -> int:
    """21 (%) → 2100 (centésimas de punto)."""
    return a_centimos(pct)  # misma escala: x100


def _aplicar_pct(importe: int, pct_basis: int) -> int:
    return round(importe * pct_basis / 10000)


def subcuenta_tercero(db: Session, tercero: models.Tercero, tipo_factura: str) -> str:
    """Devuelve (creándola si hace falta) la subcuenta 430xxxx/400xxxx del tercero."""
    if tipo_factura == "emitida":
        atributo, prefijo = "cuenta_cliente", "430"
    else:
        atributo, prefijo = "cuenta_proveedor", "400"
    codigo = getattr(tercero, atributo)
    if codigo:
        return codigo
    codigo = f"{prefijo}{tercero.id:04d}"
    if db.get(models.Cuenta, codigo) is None:
        db.add(models.Cuenta(codigo=codigo, nombre=tercero.nombre))
    setattr(tercero, atributo, codigo)
    db.flush()
    return codigo


def crear_factura(db: Session, datos: schemas.FacturaIn) -> models.Factura:
    tercero = db.get(models.Tercero, datos.tercero_id)
    if tercero is None:
        raise HTTPException(404, "Tercero no encontrado")

    duplicada = db.scalar(
        select(models.Factura).where(
            models.Factura.tipo == datos.tipo, models.Factura.numero == datos.numero
        )
    )
    if duplicada is not None:
        raise HTTPException(409, f"Ya existe la factura {datos.tipo} nº {datos.numero}")

    contrapartida = datos.cuenta_contrapartida or ("700" if datos.tipo == "emitida" else "600")
    svc_asientos.validar_cuentas(db, {contrapartida})

    lineas = [
        models.FacturaLinea(
            descripcion=li.descripcion,
            base=a_centimos(li.base),
            tipo_iva=_pct_a_basis(li.tipo_iva),
            cuota=_aplicar_pct(a_centimos(li.base), _pct_a_basis(li.tipo_iva)),
        )
        for li in datos.lineas
    ]
    base_total = sum(li.base for li in lineas)
    cuota_iva = sum(li.cuota for li in lineas)
    retencion_pct = _pct_a_basis(datos.retencion_pct)
    retencion = _aplicar_pct(base_total, retencion_pct)
    total = base_total + cuota_iva

    subcuenta = subcuenta_tercero(db, tercero, datos.tipo)
    concepto = (
        f"Fra. {'emitida' if datos.tipo == 'emitida' else 'recibida'} "
        f"{datos.numero} · {tercero.nombre}"
    )

    apuntes: list[models.Apunte] = []
    if datos.tipo == "emitida":
        apuntes.append(models.Apunte(cuenta_codigo=subcuenta, debe=total - retencion))
        if retencion:
            apuntes.append(
                models.Apunte(cuenta_codigo=CUENTA_RETENCION_SOPORTADA, debe=retencion)
            )
        apuntes.append(models.Apunte(cuenta_codigo=contrapartida, haber=base_total))
        if cuota_iva:
            apuntes.append(models.Apunte(cuenta_codigo=CUENTA_IVA_REPERCUTIDO, haber=cuota_iva))
    else:
        apuntes.append(models.Apunte(cuenta_codigo=contrapartida, debe=base_total))
        if cuota_iva:
            apuntes.append(models.Apunte(cuenta_codigo=CUENTA_IVA_SOPORTADO, debe=cuota_iva))
        apuntes.append(models.Apunte(cuenta_codigo=subcuenta, haber=total - retencion))
        if retencion:
            apuntes.append(
                models.Apunte(cuenta_codigo=CUENTA_RETENCION_PRACTICADA, haber=retencion)
            )
    for apunte in apuntes:
        apunte.concepto = concepto

    asiento = svc_asientos.crear_asiento_directo(db, datos.fecha, concepto, apuntes)

    factura = models.Factura(
        tipo=datos.tipo,
        numero=datos.numero,
        fecha=datos.fecha,
        tercero_id=tercero.id,
        cuenta_contrapartida=contrapartida,
        retencion_pct=retencion_pct,
        base_total=base_total,
        cuota_iva=cuota_iva,
        retencion_importe=retencion,
        total=total,
        asiento_id=asiento.id,
        lineas=lineas,
    )
    db.add(factura)
    db.commit()
    return factura


def liquidar_factura(db: Session, factura_id: int, datos: schemas.LiquidarIn) -> models.Factura:
    factura = db.get(models.Factura, factura_id)
    if factura is None:
        raise HTTPException(404, "Factura no encontrada")
    if factura.estado == "pagada":
        raise HTTPException(409, "La factura ya está liquidada")
    svc_asientos.validar_cuentas(db, {datos.cuenta_tesoreria})

    tercero = factura.tercero
    subcuenta = subcuenta_tercero(db, tercero, factura.tipo)
    importe = factura.total - factura.retencion_importe
    verbo = "Cobro" if factura.tipo == "emitida" else "Pago"
    concepto = f"{verbo} fra. {factura.numero} · {tercero.nombre}"

    if factura.tipo == "emitida":
        apuntes = [
            models.Apunte(cuenta_codigo=datos.cuenta_tesoreria, debe=importe, concepto=concepto),
            models.Apunte(cuenta_codigo=subcuenta, haber=importe, concepto=concepto),
        ]
    else:
        apuntes = [
            models.Apunte(cuenta_codigo=subcuenta, debe=importe, concepto=concepto),
            models.Apunte(cuenta_codigo=datos.cuenta_tesoreria, haber=importe, concepto=concepto),
        ]
    asiento = svc_asientos.crear_asiento_directo(db, datos.fecha, concepto, apuntes)
    factura.asiento_pago_id = asiento.id
    factura.estado = "pagada"
    db.commit()
    return factura


def eliminar_factura(db: Session, factura_id: int) -> None:
    factura = db.get(models.Factura, factura_id)
    if factura is None:
        raise HTTPException(404, "Factura no encontrada")
    asiento_ids = [i for i in (factura.asiento_id, factura.asiento_pago_id) if i is not None]
    db.delete(factura)
    db.flush()
    for asiento_id in asiento_ids:
        asiento = db.get(models.Asiento, asiento_id)
        if asiento is not None:
            db.delete(asiento)
    db.commit()


def serializar(factura: models.Factura) -> dict:
    return {
        "id": factura.id,
        "tipo": factura.tipo,
        "numero": factura.numero,
        "fecha": factura.fecha,
        "tercero_id": factura.tercero_id,
        "tercero_nombre": factura.tercero.nombre,
        "cuenta_contrapartida": factura.cuenta_contrapartida,
        "retencion_pct": factura.retencion_pct / 100,
        "base_total": a_euros(factura.base_total),
        "cuota_iva": a_euros(factura.cuota_iva),
        "retencion_importe": a_euros(factura.retencion_importe),
        "total": a_euros(factura.total),
        "estado": factura.estado,
        "asiento_id": factura.asiento_id,
        "asiento_pago_id": factura.asiento_pago_id,
        "lineas": [
            {
                "descripcion": li.descripcion,
                "base": a_euros(li.base),
                "tipo_iva": li.tipo_iva / 100,
                "cuota": a_euros(li.cuota),
            }
            for li in factura.lineas
        ],
    }
