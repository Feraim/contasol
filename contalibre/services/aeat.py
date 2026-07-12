"""Modelos oficiales AEAT simplificados a partir de los datos contables.

Estos informes reproducen la estructura de casillas de los modelos 303,
390 y 347, pero no cubren todos los regímenes ni claves del formulario
oficial (ver aviso en cada resultado). No sustituyen la presentación
real ante la Agencia Tributaria.
"""

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..money import a_euros
from .informes import resumen_iva

UMBRAL_347 = 300506  # céntimos: 3.005,06 €

AVISO_303 = (
    "Modelo simplificado (régimen general): no incluye operaciones intracomunitarias, "
    "importaciones, bienes de inversión, recargo de equivalencia ni compensación de "
    "cuotas de periodos anteriores."
)
AVISO_390 = (
    "Resumen informativo anual a partir de los cuatro trimestres; no incluye prorratas, "
    "regularizaciones de bienes de inversión ni todas las claves del formulario oficial."
)
AVISO_347 = (
    "Umbral legal de 3.005,06 € anuales por tercero y tipo de operación (IVA incluido). "
    "No distingue operaciones en metálico, seguros, arrendamientos u otras claves especiales."
)


def modelo_303(db: Session, ejercicio: int, trimestre: int) -> dict:
    resumen = resumen_iva(db, ejercicio, trimestre)
    cuota_devengada = round(resumen["repercutido"]["cuota"], 2)
    base_deducible = round(resumen["soportado"]["base"], 2)
    cuota_deducible = round(resumen["soportado"]["cuota"], 2)
    resultado = round(cuota_devengada - cuota_deducible, 2)
    if resultado == 0:
        sentido = "sin actividad"
    elif resultado > 0:
        sentido = "a ingresar"
    else:
        sentido = "a devolver" if trimestre == 4 else "a compensar"
    return {
        "modelo": "303",
        "ejercicio": ejercicio,
        "trimestre": trimestre,
        "desde": resumen["desde"],
        "hasta": resumen["hasta"],
        "iva_devengado": {
            "desglose": resumen["repercutido"]["desglose"],
            "casilla_27_cuota_devengada": cuota_devengada,
        },
        "iva_deducible": {
            "casilla_28_base": base_deducible,
            "casilla_29_cuota": cuota_deducible,
            "casilla_44_total_a_deducir": cuota_deducible,
        },
        "casilla_46_resultado_regimen_general": resultado,
        "casilla_69_resultado_liquidacion": resultado,
        "sentido": sentido,
        "aviso": AVISO_303,
    }


def modelo_390(db: Session, ejercicio: int) -> dict:
    trimestrales = [resumen_iva(db, ejercicio, t) for t in (1, 2, 3, 4)]

    def _fusionar(clave: str) -> list[dict]:
        por_tipo: dict[float, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for r in trimestrales:
            for fila in r[clave]["desglose"]:
                por_tipo[fila["tipo_iva"]][0] += fila["base"]
                por_tipo[fila["tipo_iva"]][1] += fila["cuota"]
        return [
            {"tipo_iva": t, "base": round(b, 2), "cuota": round(c, 2)}
            for t, (b, c) in sorted(por_tipo.items(), reverse=True)
        ]

    total_devengado = round(sum(r["repercutido"]["cuota"] for r in trimestrales), 2)
    total_deducible = round(sum(r["soportado"]["cuota"] for r in trimestrales), 2)
    return {
        "modelo": "390",
        "ejercicio": ejercicio,
        "iva_devengado": _fusionar("repercutido"),
        "iva_deducible": _fusionar("soportado"),
        "total_devengado": total_devengado,
        "total_deducible": total_deducible,
        "resultado_anual": round(total_devengado - total_deducible, 2),
        "resultados_trimestrales": [
            {"trimestre": r["trimestre"], "resultado": r["resultado"], "sentido": r["sentido"]}
            for r in trimestrales
        ],
        "aviso": AVISO_390,
    }


def modelo_347(db: Session, ejercicio: int) -> dict:
    inicio, fin = date(ejercicio, 1, 1), date(ejercicio, 12, 31)
    facturas = db.scalars(
        select(models.Factura).where(models.Factura.fecha >= inicio, models.Factura.fecha <= fin)
    ).all()

    acumulado: dict[tuple[int, str], dict] = {}
    for f in facturas:
        clave = (f.tercero_id, f.tipo)
        trimestre = (f.fecha.month - 1) // 3 + 1
        entrada = acumulado.setdefault(
            clave, {"total": 0, "trimestres": {1: 0, 2: 0, 3: 0, 4: 0}}
        )
        entrada["total"] += f.total
        entrada["trimestres"][trimestre] += f.total

    terceros_ids = {clave[0] for clave in acumulado}
    nombres = {
        t.id: (t.nombre, t.nif)
        for t in db.scalars(select(models.Tercero).where(models.Tercero.id.in_(terceros_ids)))
    }

    registros = []
    for (tercero_id, tipo), datos in acumulado.items():
        if datos["total"] < UMBRAL_347:
            continue
        nombre, nif = nombres.get(tercero_id, ("", ""))
        registros.append(
            {
                "tercero_id": tercero_id,
                "nif": nif,
                "nombre": nombre,
                "clave": "A" if tipo == "recibida" else "B",
                "operacion": "compras" if tipo == "recibida" else "ventas",
                "importe_anual": a_euros(datos["total"]),
                "trimestres": {str(t): a_euros(v) for t, v in datos["trimestres"].items()},
            }
        )
    registros.sort(key=lambda r: (-r["importe_anual"], r["nombre"]))
    return {
        "modelo": "347",
        "ejercicio": ejercicio,
        "umbral": a_euros(UMBRAL_347),
        "registros": registros,
        "total_declarado": round(sum(r["importe_anual"] for r in registros), 2),
        "aviso": AVISO_347,
    }
