"""Herramientas de solo lectura para el asistente de IA (tool calling).

Cada función envuelve una consulta ya existente (o una muy parecida a la
que usan los routers) y devuelve datos JSON-serializables. El modelo de
IA nunca toca la base de datos directamente: solo puede pedir una de
estas herramientas, acotadas siempre a la empresa activa de la sesión
que hizo la pregunta (la misma `db` que usa el resto de la aplicación).
"""

from datetime import date

from sqlalchemy import select

from .. import models
from . import aeat as svc_aeat
from . import amortizacion as svc_amortizacion
from . import asientos as svc_asientos
from . import cierre as svc_cierre
from . import conciliacion as svc_conciliacion
from . import facturas as svc_facturas
from . import informes as svc_informes

DESCRIPCION_ESQUEMA = {
    "software": "ContaLibre: contabilidad española (PGC) de código abierto",
    "convenciones": {
        "importes": "euros con 2 decimales",
        "cuentas": "códigos numéricos del PGC; subcuentas de clientes 430xxxx y de proveedores 400xxxx",
        "partida_doble": "todo asiento cumple suma(debe) == suma(haber)",
        "fechas": "formato ISO AAAA-MM-DD",
    },
    "entidades": {
        "cuentas": "plan contable: codigo, nombre",
        "asientos": "asiento del diario: numero (por ejercicio), fecha, concepto, apuntes[]",
        "apuntes": "línea de asiento: cuenta, concepto, debe, haber",
        "terceros": "clientes/proveedores: nif, nombre, subcuentas contables",
        "facturas": "emitidas/recibidas con líneas (base, tipo_iva, cuota), retención, estado y asiento vinculado",
        "activos": "inmovilizado con plan de amortización lineal y dotaciones por ejercicio",
        "ejercicios": "estado de cierre/apertura por año: regularización 6/7 contra 129 y cierre de balance",
        "movimientos_bancarios": "extracto importado (norma 43): fecha, concepto, importe con signo, conciliado, apunte vinculado",
    },
}


def _fecha(valor: str | None) -> date | None:
    return date.fromisoformat(valor) if valor else None


def buscar_cuentas(db, q: str | None = None) -> list[dict]:
    consulta = select(models.Cuenta).order_by(models.Cuenta.codigo)
    if q:
        consulta = consulta.where(
            models.Cuenta.codigo.startswith(q) | models.Cuenta.nombre.icontains(q)
        )
    return [{"codigo": c.codigo, "nombre": c.nombre} for c in db.scalars(consulta).all()[:200]]


def listar_terceros(db, q: str | None = None, tipo: str | None = None) -> list[dict]:
    consulta = select(models.Tercero).order_by(models.Tercero.nombre)
    if q:
        consulta = consulta.where(
            models.Tercero.nombre.icontains(q) | models.Tercero.nif.icontains(q)
        )
    if tipo in ("cliente", "proveedor"):
        consulta = consulta.where(models.Tercero.tipo.in_((tipo, "ambos")))
    return [
        {
            "id": t.id, "tipo": t.tipo, "nif": t.nif, "nombre": t.nombre,
            "cuenta_cliente": t.cuenta_cliente, "cuenta_proveedor": t.cuenta_proveedor,
        }
        for t in db.scalars(consulta).all()[:200]
    ]


def listar_asientos(
    db, desde: str | None = None, hasta: str | None = None, cuenta: str | None = None,
    limite: int = 50,
) -> list[dict]:
    consulta = select(models.Asiento).order_by(
        models.Asiento.fecha.desc(), models.Asiento.numero.desc()
    )
    if desde:
        consulta = consulta.where(models.Asiento.fecha >= _fecha(desde))
    if hasta:
        consulta = consulta.where(models.Asiento.fecha <= _fecha(hasta))
    if cuenta:
        consulta = (
            consulta.join(models.Apunte)
            .where(models.Apunte.cuenta_codigo.startswith(cuenta))
            .distinct()
        )
    consulta = consulta.limit(min(limite, 200))
    return [svc_asientos.serializar(db, a) for a in db.scalars(consulta).unique()]


def listar_facturas(
    db, tipo: str | None = None, estado: str | None = None,
    desde: str | None = None, hasta: str | None = None,
) -> list[dict]:
    consulta = select(models.Factura).order_by(models.Factura.fecha.desc(), models.Factura.id.desc())
    if tipo in ("emitida", "recibida"):
        consulta = consulta.where(models.Factura.tipo == tipo)
    if estado in ("pendiente", "pagada"):
        consulta = consulta.where(models.Factura.estado == estado)
    if desde:
        consulta = consulta.where(models.Factura.fecha >= _fecha(desde))
    if hasta:
        consulta = consulta.where(models.Factura.fecha <= _fecha(hasta))
    return [svc_facturas.serializar(f) for f in db.scalars(consulta).all()[:200]]


def listar_activos(db) -> list[dict]:
    return [
        svc_amortizacion.serializar(a)
        for a in db.scalars(select(models.Activo).order_by(models.Activo.id)).all()
    ]


def listar_movimientos_bancarios(
    db, cuenta: str | None = None, conciliado: bool | None = None,
    desde: str | None = None, hasta: str | None = None,
) -> list[dict]:
    return [
        svc_conciliacion.serializar(m)
        for m in svc_conciliacion.listar(db, cuenta, conciliado, _fecha(desde), _fecha(hasta))
    ]


def listar_ejercicios(db) -> list[dict]:
    return svc_cierre.listar(db)


def informe_libro_mayor(db, cuenta: str, desde: str | None = None, hasta: str | None = None) -> dict:
    return svc_informes.mayor(db, cuenta, _fecha(desde), _fecha(hasta))


def informe_sumas_y_saldos(db, desde: str | None = None, hasta: str | None = None) -> dict:
    return svc_informes.sumas_y_saldos(db, _fecha(desde), _fecha(hasta))


def informe_perdidas_y_ganancias(db, desde: str | None = None, hasta: str | None = None) -> dict:
    return svc_informes.perdidas_y_ganancias(db, _fecha(desde), _fecha(hasta))


def informe_balance_situacion(db, hasta: str | None = None) -> dict:
    return svc_informes.balance_situacion(db, _fecha(hasta))


def informe_iva_trimestral(db, ejercicio: int, trimestre: int) -> dict:
    return svc_informes.resumen_iva(db, ejercicio, trimestre)


def resumen_panel(db) -> dict:
    return svc_informes.panel(db)


def modelo_aeat_303(db, ejercicio: int, trimestre: int) -> dict:
    return svc_aeat.modelo_303(db, ejercicio, trimestre)


def modelo_aeat_390(db, ejercicio: int) -> dict:
    return svc_aeat.modelo_390(db, ejercicio)


def modelo_aeat_347(db, ejercicio: int) -> dict:
    return svc_aeat.modelo_347(db, ejercicio)


# (nombre, función, esquema de parámetros JSON estilo OpenAI/Ollama function-calling)
_DEFS = [
    ("buscar_cuentas", buscar_cuentas, {"q": "texto o prefijo de código a buscar (opcional)"}),
    (
        "listar_terceros", listar_terceros,
        {"q": "texto a buscar en nombre o NIF (opcional)", "tipo": "'cliente' o 'proveedor' (opcional)"},
    ),
    (
        "listar_asientos", listar_asientos,
        {
            "desde": "fecha ISO desde (opcional)", "hasta": "fecha ISO hasta (opcional)",
            "cuenta": "prefijo de cuenta para filtrar (opcional)",
            "limite": "número máximo de asientos a devolver (opcional, por defecto 50)",
        },
    ),
    (
        "listar_facturas", listar_facturas,
        {
            "tipo": "'emitida' o 'recibida' (opcional)",
            "estado": "'pendiente' o 'pagada' (opcional)",
            "desde": "fecha ISO desde (opcional)", "hasta": "fecha ISO hasta (opcional)",
        },
    ),
    ("listar_activos", listar_activos, {}),
    (
        "listar_movimientos_bancarios", listar_movimientos_bancarios,
        {
            "cuenta": "código de cuenta de tesorería, p.ej. 572 (opcional)",
            "conciliado": "true/false para filtrar por estado de conciliación (opcional)",
            "desde": "fecha ISO desde (opcional)", "hasta": "fecha ISO hasta (opcional)",
        },
    ),
    ("listar_ejercicios", listar_ejercicios, {}),
    (
        "informe_libro_mayor", informe_libro_mayor,
        {
            "cuenta": "código o prefijo de cuenta (obligatorio)",
            "desde": "fecha ISO desde (opcional)", "hasta": "fecha ISO hasta (opcional)",
        },
    ),
    (
        "informe_sumas_y_saldos", informe_sumas_y_saldos,
        {"desde": "fecha ISO desde (opcional)", "hasta": "fecha ISO hasta (opcional)"},
    ),
    (
        "informe_perdidas_y_ganancias", informe_perdidas_y_ganancias,
        {"desde": "fecha ISO desde (opcional)", "hasta": "fecha ISO hasta (opcional)"},
    ),
    ("informe_balance_situacion", informe_balance_situacion, {"hasta": "fecha ISO (opcional)"}),
    (
        "informe_iva_trimestral", informe_iva_trimestral,
        {"ejercicio": "año, p.ej. 2026 (obligatorio)", "trimestre": "1, 2, 3 o 4 (obligatorio)"},
    ),
    ("resumen_panel", resumen_panel, {}),
    (
        "modelo_aeat_303", modelo_aeat_303,
        {"ejercicio": "año (obligatorio)", "trimestre": "1, 2, 3 o 4 (obligatorio)"},
    ),
    ("modelo_aeat_390", modelo_aeat_390, {"ejercicio": "año (obligatorio)"}),
    ("modelo_aeat_347", modelo_aeat_347, {"ejercicio": "año (obligatorio)"}),
]

_OBLIGATORIOS = {
    "informe_libro_mayor": ["cuenta"],
    "informe_iva_trimestral": ["ejercicio", "trimestre"],
    "modelo_aeat_303": ["ejercicio", "trimestre"],
    "modelo_aeat_390": ["ejercicio"],
    "modelo_aeat_347": ["ejercicio"],
}

_DESCRIPCIONES = {
    "buscar_cuentas": "Busca cuentas del plan contable por código o nombre.",
    "listar_terceros": "Lista clientes y/o proveedores.",
    "listar_asientos": "Lista asientos del diario, opcionalmente filtrados por fecha o cuenta.",
    "listar_facturas": "Lista facturas emitidas y/o recibidas.",
    "listar_activos": "Lista el inmovilizado con su amortización acumulada y valor neto.",
    "listar_movimientos_bancarios": "Lista movimientos bancarios importados y su estado de conciliación.",
    "listar_ejercicios": "Lista el estado de cierre/apertura de cada ejercicio (año).",
    "informe_libro_mayor": "Libro mayor de una cuenta: todos sus movimientos y saldo acumulado.",
    "informe_sumas_y_saldos": "Balance de sumas y saldos de todas las cuentas.",
    "informe_perdidas_y_ganancias": "Cuenta de pérdidas y ganancias (ingresos, gastos, resultado).",
    "informe_balance_situacion": "Balance de situación con la estructura oficial del PGC.",
    "informe_iva_trimestral": "Resumen de IVA repercutido/soportado de un trimestre.",
    "resumen_panel": "Resumen general: resultado del ejercicio, tesorería, pendientes de cobro/pago, IVA del trimestre.",
    "modelo_aeat_303": "Modelo 303 (liquidación trimestral de IVA) simplificado.",
    "modelo_aeat_390": "Modelo 390 (resumen anual de IVA) simplificado.",
    "modelo_aeat_347": "Modelo 347 (operaciones con terceros > 3.005,06 €/año) simplificado.",
}

TOOL_DISPATCH = {nombre: fn for nombre, fn, _ in _DEFS}


def _json_schema(nombre: str, parametros: dict[str, str]) -> dict:
    obligatorios = _OBLIGATORIOS.get(nombre, [])
    propiedades = {}
    for campo, descripcion in parametros.items():
        tipo = "integer" if campo in ("trimestre", "ejercicio", "limite") else (
            "boolean" if campo == "conciliado" else "string"
        )
        propiedades[campo] = {"type": tipo, "description": descripcion}
    return {
        "type": "function",
        "function": {
            "name": nombre,
            "description": _DESCRIPCIONES[nombre],
            "parameters": {
                "type": "object",
                "properties": propiedades,
                "required": obligatorios,
            },
        },
    }


TOOL_SCHEMAS = [_json_schema(nombre, parametros) for nombre, _, parametros in _DEFS]


def ejecutar_tool(db, nombre: str, argumentos: dict) -> dict:
    """Ejecuta una herramienta por nombre. Nunca lanza: cualquier error se
    devuelve como {"error": "..."} para que el modelo pueda leerlo y
    reformular en vez de romper la conversación."""
    fn = TOOL_DISPATCH.get(nombre)
    if fn is None:
        return {"error": f"Herramienta desconocida: {nombre}"}
    try:
        resultado = fn(db, **argumentos)
    except TypeError as exc:
        return {"error": f"Argumentos inválidos para {nombre}: {exc}"}
    except Exception as exc:  # noqa: BLE001 — el modelo debe poder ver cualquier fallo
        return {"error": f"Error ejecutando {nombre}: {exc}"}
    return {"resultado": resultado}
