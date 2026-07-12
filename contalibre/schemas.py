from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

# La API habla en euros (números con 2 decimales); internamente todo son céntimos.


class CuentaIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=10, pattern=r"^\d+$")
    nombre: str = Field(min_length=1, max_length=120)


class CuentaOut(CuentaIn):
    model_config = {"from_attributes": True}


class ApunteIn(BaseModel):
    cuenta: str = Field(min_length=1, max_length=10)
    concepto: str = ""
    debe: Decimal = Decimal("0")
    haber: Decimal = Decimal("0")

    @field_validator("debe", "haber")
    @classmethod
    def _no_negativo(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("los importes no pueden ser negativos")
        return v


class AsientoIn(BaseModel):
    fecha: date
    concepto: str = Field(min_length=1, max_length=200)
    apuntes: list[ApunteIn] = Field(min_length=2)


class ApunteOut(BaseModel):
    id: int
    cuenta: str
    cuenta_nombre: str
    concepto: str
    debe: float
    haber: float


class AsientoOut(BaseModel):
    id: int
    numero: int
    fecha: date
    concepto: str
    apuntes: list[ApunteOut]


class TerceroIn(BaseModel):
    tipo: str = Field(pattern=r"^(cliente|proveedor|ambos)$")
    nif: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=150)
    direccion: str = ""
    email: str = ""
    telefono: str = ""


class TerceroOut(TerceroIn):
    model_config = {"from_attributes": True}

    id: int
    cuenta_cliente: str | None = None
    cuenta_proveedor: str | None = None


class FacturaLineaIn(BaseModel):
    descripcion: str = Field(min_length=1, max_length=200)
    base: Decimal
    tipo_iva: Decimal = Decimal("21")  # porcentaje: 21, 10, 4, 0…

    @field_validator("base")
    @classmethod
    def _base_positiva(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("la base debe ser positiva")
        return v

    @field_validator("tipo_iva")
    @classmethod
    def _iva_valido(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("tipo de IVA inválido")
        return v


class FacturaIn(BaseModel):
    tipo: str = Field(pattern=r"^(emitida|recibida)$")
    numero: str = Field(min_length=1, max_length=30)
    fecha: date
    tercero_id: int
    # Por defecto: 700 (ventas) en emitidas, 600 (compras) en recibidas
    cuenta_contrapartida: str | None = None
    retencion_pct: Decimal = Decimal("0")
    lineas: list[FacturaLineaIn] = Field(min_length=1)

    @field_validator("retencion_pct")
    @classmethod
    def _retencion_valida(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("retención inválida")
        return v


class FacturaLineaOut(BaseModel):
    descripcion: str
    base: float
    tipo_iva: float
    cuota: float


class FacturaOut(BaseModel):
    id: int
    tipo: str
    numero: str
    fecha: date
    tercero_id: int
    tercero_nombre: str
    cuenta_contrapartida: str
    retencion_pct: float
    base_total: float
    cuota_iva: float
    retencion_importe: float
    total: float
    estado: str
    asiento_id: int | None
    asiento_pago_id: int | None
    lineas: list[FacturaLineaOut]


class LiquidarIn(BaseModel):
    fecha: date
    cuenta_tesoreria: str = "572"


class ActivoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    fecha_adquisicion: date
    valor: Decimal
    valor_residual: Decimal = Decimal("0")
    vida_util_anios: int = Field(gt=0, le=100)
    cuenta_activo: str = "213"
    cuenta_amort_acum: str = "281"
    cuenta_gasto: str = "681"

    @field_validator("valor")
    @classmethod
    def _valor_positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("el valor debe ser positivo")
        return v


class AmortizacionOut(BaseModel):
    ejercicio: int
    importe: float
    asiento_id: int | None


class ActivoOut(BaseModel):
    id: int
    nombre: str
    fecha_adquisicion: date
    valor: float
    valor_residual: float
    vida_util_anios: int
    cuenta_activo: str
    cuenta_amort_acum: str
    cuenta_gasto: str
    amortizado: float
    valor_neto: float
    amortizaciones: list[AmortizacionOut]


class AmortizarIn(BaseModel):
    ejercicio: int = Field(ge=1900, le=2200)


class ImportarNorma43In(BaseModel):
    cuenta_tesoreria: str = Field(min_length=1, max_length=10)
    contenido: str = Field(min_length=1)


class ConciliarIn(BaseModel):
    apunte_id: int


class ConciliarNuevoIn(BaseModel):
    cuenta_contrapartida: str = Field(min_length=1, max_length=10)
    concepto: str = ""


class MovimientoBancarioOut(BaseModel):
    id: int
    cuenta_tesoreria: str
    fecha_operacion: date
    fecha_valor: date
    concepto: str
    importe: float
    documento: str
    referencia: str
    conciliado: bool
    apunte_id: int | None


class EjercicioOut(BaseModel):
    anio: int
    abierto: bool
    cerrado: bool
    fecha_apertura: date | None
    fecha_cierre: date | None
    resultado: float | None
    resultado_previsto: float | None = None
    asiento_apertura_id: int | None
    asiento_regularizacion_id: int | None
    asiento_cierre_id: int | None
