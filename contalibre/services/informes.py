from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..money import a_euros


def _saldos(db: Session, desde: date | None, hasta: date | None) -> dict[str, tuple[int, int]]:
    """Suma de debe/haber por cuenta en el rango de fechas (céntimos)."""
    q = (
        select(
            models.Apunte.cuenta_codigo,
            func.sum(models.Apunte.debe),
            func.sum(models.Apunte.haber),
        )
        .join(models.Asiento)
        .group_by(models.Apunte.cuenta_codigo)
    )
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)
    return {codigo: (debe or 0, haber or 0) for codigo, debe, haber in db.execute(q)}


def _nombres(db: Session, codigos) -> dict[str, str]:
    if not codigos:
        return {}
    return {
        c.codigo: c.nombre
        for c in db.scalars(select(models.Cuenta).where(models.Cuenta.codigo.in_(codigos)))
    }


def mayor(
    db: Session, cuenta: str, desde: date | None = None, hasta: date | None = None
) -> dict:
    """Libro mayor de una cuenta (o prefijo de cuenta) con saldo acumulado."""
    q = (
        select(models.Apunte, models.Asiento)
        .join(models.Asiento)
        .where(models.Apunte.cuenta_codigo.startswith(cuenta))
        .order_by(models.Asiento.fecha, models.Asiento.numero, models.Apunte.id)
    )
    if desde:
        q = q.where(models.Asiento.fecha >= desde)
    if hasta:
        q = q.where(models.Asiento.fecha <= hasta)

    movimientos = []
    saldo = 0
    total_debe = total_haber = 0
    for apunte, asiento in db.execute(q):
        saldo += apunte.debe - apunte.haber
        total_debe += apunte.debe
        total_haber += apunte.haber
        movimientos.append(
            {
                "fecha": asiento.fecha,
                "asiento": asiento.numero,
                "asiento_id": asiento.id,
                "cuenta": apunte.cuenta_codigo,
                "concepto": apunte.concepto or asiento.concepto,
                "debe": a_euros(apunte.debe),
                "haber": a_euros(apunte.haber),
                "saldo": a_euros(saldo),
            }
        )
    nombre = _nombres(db, [cuenta]).get(cuenta, "")
    return {
        "cuenta": cuenta,
        "nombre": nombre,
        "movimientos": movimientos,
        "total_debe": a_euros(total_debe),
        "total_haber": a_euros(total_haber),
        "saldo": a_euros(saldo),
    }


def sumas_y_saldos(db: Session, desde: date | None = None, hasta: date | None = None) -> dict:
    saldos = _saldos(db, desde, hasta)
    nombres = _nombres(db, list(saldos))
    filas = []
    total_debe = total_haber = 0
    for codigo in sorted(saldos):
        debe, haber = saldos[codigo]
        total_debe += debe
        total_haber += haber
        saldo = debe - haber
        filas.append(
            {
                "cuenta": codigo,
                "nombre": nombres.get(codigo, ""),
                "debe": a_euros(debe),
                "haber": a_euros(haber),
                "saldo_deudor": a_euros(saldo) if saldo > 0 else 0,
                "saldo_acreedor": a_euros(-saldo) if saldo < 0 else 0,
            }
        )
    return {
        "filas": filas,
        "total_debe": a_euros(total_debe),
        "total_haber": a_euros(total_haber),
        "cuadrado": total_debe == total_haber,
    }


def perdidas_y_ganancias(
    db: Session, desde: date | None = None, hasta: date | None = None
) -> dict:
    saldos = _saldos(db, desde, hasta)
    nombres = _nombres(db, list(saldos))
    gastos, ingresos = [], []
    total_gastos = total_ingresos = 0
    for codigo in sorted(saldos):
        debe, haber = saldos[codigo]
        saldo = debe - haber
        if codigo.startswith("6"):
            total_gastos += saldo
            gastos.append(
                {"cuenta": codigo, "nombre": nombres.get(codigo, ""), "importe": a_euros(saldo)}
            )
        elif codigo.startswith("7"):
            total_ingresos += -saldo
            ingresos.append(
                {"cuenta": codigo, "nombre": nombres.get(codigo, ""), "importe": a_euros(-saldo)}
            )
    return {
        "gastos": gastos,
        "ingresos": ingresos,
        "total_gastos": a_euros(total_gastos),
        "total_ingresos": a_euros(total_ingresos),
        "resultado": a_euros(total_ingresos - total_gastos),
    }


# Estructura oficial del balance de situación abreviado (PGC), por epígrafe.
# Los grupos de amortización/deterioro acumulada (28, 29) se restan dentro de
# la misma masa que el activo que corrigen, no se separan aparte.
_SECCIONES_ACTIVO = [
    (("20", "280", "290"), "A) ACTIVO NO CORRIENTE · I. Inmovilizado intangible"),
    (("21", "23", "281", "291"), "A) ACTIVO NO CORRIENTE · II. Inmovilizado material"),
    (("22", "282", "292"), "A) ACTIVO NO CORRIENTE · III. Inversiones inmobiliarias"),
    (("24", "293", "294"), "A) ACTIVO NO CORRIENTE · IV. Inversiones en empresas del grupo y asociadas a largo plazo"),
    (("25", "26", "297", "298"), "A) ACTIVO NO CORRIENTE · V. Inversiones financieras a largo plazo"),
    (("474",), "A) ACTIVO NO CORRIENTE · VI. Activos por impuesto diferido"),
    (("3", "39"), "B) ACTIVO CORRIENTE · II. Existencias"),
    (
        ("43", "44", "460", "470", "471", "472", "473"),
        "B) ACTIVO CORRIENTE · III. Deudores comerciales y otras cuentas a cobrar",
    ),
    (("53",), "B) ACTIVO CORRIENTE · IV. Inversiones en empresas del grupo y asociadas a corto plazo"),
    (("54",), "B) ACTIVO CORRIENTE · V. Inversiones financieras a corto plazo"),
    (("480", "567"), "B) ACTIVO CORRIENTE · VI. Periodificaciones a corto plazo"),
    (("57",), "B) ACTIVO CORRIENTE · VII. Efectivo y otros activos líquidos equivalentes"),
]
_SECCIONES_PASIVO = [
    (("100", "101", "102", "103", "104"), "A) PATRIMONIO NETO · A-1) Fondos propios · I. Capital"),
    (("110",), "A) PATRIMONIO NETO · A-1) Fondos propios · II. Prima de emisión"),
    (("112", "113", "114", "115", "119"), "A) PATRIMONIO NETO · A-1) Fondos propios · III. Reservas"),
    (("108", "109"), "A) PATRIMONIO NETO · A-1) Fondos propios · IV. (Acciones y participaciones en patrimonio propias)"),
    (("120", "121"), "A) PATRIMONIO NETO · A-1) Fondos propios · V. Resultados de ejercicios anteriores"),
    (("118",), "A) PATRIMONIO NETO · A-1) Fondos propios · VI. Otras aportaciones de socios"),
    (("129",), "A) PATRIMONIO NETO · A-1) Fondos propios · VII. Resultado del ejercicio"),
    (("557",), "A) PATRIMONIO NETO · A-1) Fondos propios · VIII. (Dividendo a cuenta)"),
    (("133", "134", "135", "136", "137"), "A) PATRIMONIO NETO · A-2) Ajustes por cambios de valor"),
    (("130", "131", "132"), "A) PATRIMONIO NETO · A-3) Subvenciones, donaciones y legados recibidos"),
    (("14",), "B) PASIVO NO CORRIENTE · I. Provisiones a largo plazo"),
    (("15", "17", "18"), "B) PASIVO NO CORRIENTE · II. Deudas a largo plazo"),
    (("16",), "B) PASIVO NO CORRIENTE · III. Deudas con empresas del grupo y asociadas a largo plazo"),
    (("479",), "B) PASIVO NO CORRIENTE · IV. Pasivos por impuesto diferido"),
    (("499", "529"), "C) PASIVO CORRIENTE · I. Provisiones a corto plazo"),
    (("50", "52", "55", "560", "561"), "C) PASIVO CORRIENTE · II. Deudas a corto plazo"),
    (("51",), "C) PASIVO CORRIENTE · III. Deudas con empresas del grupo y asociadas a corto plazo"),
    (
        ("40", "41", "438", "465", "466", "475", "476", "477"),
        "C) PASIVO CORRIENTE · IV. Acreedores comerciales y otras cuentas a pagar",
    ),
    (("485", "568"), "C) PASIVO CORRIENTE · V. Periodificaciones a corto plazo"),
]


def _clasificar(codigo: str) -> tuple[str, str] | None:
    """Devuelve (lado, sección) para un código, mirando primero prefijos largos."""
    candidatos = []
    for prefijos, seccion in _SECCIONES_ACTIVO:
        for p in prefijos:
            candidatos.append((p, "activo", seccion))
    for prefijos, seccion in _SECCIONES_PASIVO:
        for p in prefijos:
            candidatos.append((p, "pasivo", seccion))
    candidatos.sort(key=lambda t: len(t[0]), reverse=True)
    for prefijo, lado, seccion in candidatos:
        if codigo.startswith(prefijo):
            return lado, seccion
    return None


def balance_situacion(db: Session, hasta: date | None = None) -> dict:
    saldos = _saldos(db, None, hasta)
    nombres = _nombres(db, list(saldos))
    activo: dict[str, list] = defaultdict(list)
    pasivo: dict[str, list] = defaultdict(list)
    total_activo = total_pasivo = 0
    resultado = 0  # grupos 6 y 7 sin regularizar

    for codigo in sorted(saldos):
        debe, haber = saldos[codigo]
        saldo = debe - haber
        if saldo == 0:
            continue
        if codigo.startswith(("6", "7")):
            resultado += -saldo
            continue
        destino = _clasificar(codigo)
        if destino is None:
            destino = (
                ("activo", "B) ACTIVO CORRIENTE · Otros activos sin clasificar")
                if saldo > 0
                else ("pasivo", "C) PASIVO CORRIENTE · Otros pasivos sin clasificar")
            )
        lado, seccion = destino
        fila = {"cuenta": codigo, "nombre": nombres.get(codigo, "")}
        if lado == "activo":
            fila["importe"] = a_euros(saldo)
            activo[seccion].append(fila)
            total_activo += saldo
        else:
            fila["importe"] = a_euros(-saldo)
            pasivo[seccion].append(fila)
            total_pasivo += -saldo

    if resultado:
        seccion_resultado = "A) PATRIMONIO NETO · A-1) Fondos propios · VII. Resultado del ejercicio"
        pasivo[seccion_resultado].append(
            {"cuenta": "", "nombre": "Resultado del periodo (sin regularizar)",
             "importe": a_euros(resultado)}
        )
        total_pasivo += resultado

    return {
        "activo": dict(activo),
        "pasivo": dict(pasivo),
        "total_activo": a_euros(total_activo),
        "total_pasivo": a_euros(total_pasivo),
        "cuadrado": total_activo == total_pasivo,
    }


def _rango_trimestre(ejercicio: int, trimestre: int) -> tuple[date, date]:
    inicio = date(ejercicio, 3 * (trimestre - 1) + 1, 1)
    fin = (
        date(ejercicio, 12, 31)
        if trimestre == 4
        else date(ejercicio, 3 * trimestre + 1, 1) - timedelta(days=1)
    )
    return inicio, fin


def resumen_iva(db: Session, ejercicio: int, trimestre: int) -> dict:
    """Resumen tipo modelo 303 a partir de las facturas del trimestre."""
    desde, hasta = _rango_trimestre(ejercicio, trimestre)
    facturas = db.scalars(
        select(models.Factura).where(models.Factura.fecha >= desde, models.Factura.fecha <= hasta)
    ).all()

    def _desglose(tipo: str) -> tuple[list, int, int]:
        por_tipo: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        for f in facturas:
            if f.tipo != tipo:
                continue
            for li in f.lineas:
                por_tipo[li.tipo_iva][0] += li.base
                por_tipo[li.tipo_iva][1] += li.cuota
        filas = [
            {"tipo_iva": t / 100, "base": a_euros(b), "cuota": a_euros(c)}
            for t, (b, c) in sorted(por_tipo.items(), reverse=True)
        ]
        return (
            filas,
            sum(v[0] for v in por_tipo.values()),
            sum(v[1] for v in por_tipo.values()),
        )

    rep_filas, rep_base, rep_cuota = _desglose("emitida")
    sop_filas, sop_base, sop_cuota = _desglose("recibida")
    return {
        "ejercicio": ejercicio,
        "trimestre": trimestre,
        "desde": desde,
        "hasta": hasta,
        "repercutido": {"desglose": rep_filas, "base": a_euros(rep_base), "cuota": a_euros(rep_cuota)},
        "soportado": {"desglose": sop_filas, "base": a_euros(sop_base), "cuota": a_euros(sop_cuota)},
        "resultado": a_euros(rep_cuota - sop_cuota),
        "sentido": "a ingresar" if rep_cuota >= sop_cuota else "a compensar/devolver",
    }


def panel(db: Session, hoy: date | None = None) -> dict:
    """Resumen para la pantalla de inicio."""
    hoy = hoy or date.today()
    inicio_anio = date(hoy.year, 1, 1)
    pyg = perdidas_y_ganancias(db, inicio_anio, hoy)

    saldos = _saldos(db, None, hoy)
    tesoreria = sum(d - h for c, (d, h) in saldos.items() if c.startswith("57"))

    pendientes = db.scalars(
        select(models.Factura).where(models.Factura.estado == "pendiente")
    ).all()
    cobrar = sum(f.total - f.retencion_importe for f in pendientes if f.tipo == "emitida")
    pagar = sum(f.total - f.retencion_importe for f in pendientes if f.tipo == "recibida")

    trimestre = (hoy.month - 1) // 3 + 1
    iva = resumen_iva(db, hoy.year, trimestre)

    num_asientos = db.scalar(select(func.count(models.Asiento.id))) or 0
    return {
        "fecha": hoy,
        "ejercicio": hoy.year,
        "resultado_ejercicio": pyg["resultado"],
        "ingresos_ejercicio": pyg["total_ingresos"],
        "gastos_ejercicio": pyg["total_gastos"],
        "tesoreria": a_euros(tesoreria),
        "pendiente_cobro": a_euros(cobrar),
        "pendiente_pago": a_euros(pagar),
        "facturas_pendientes": len(pendientes),
        "iva_trimestre": {"trimestre": trimestre, "resultado": iva["resultado"]},
        "num_asientos": num_asientos,
    }
