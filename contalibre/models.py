from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Todos los importes se guardan en céntimos (int); los tipos de IVA y
# retención en centésimas de punto porcentual (2100 = 21,00 %).


class Cuenta(Base):
    __tablename__ = "cuentas"

    codigo: Mapped[str] = mapped_column(String(10), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))


class Asiento(Base):
    __tablename__ = "asientos"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    concepto: Mapped[str] = mapped_column(String(200))

    apuntes: Mapped[list["Apunte"]] = relationship(
        back_populates="asiento", cascade="all, delete-orphan", order_by="Apunte.id"
    )


class Apunte(Base):
    __tablename__ = "apuntes"

    id: Mapped[int] = mapped_column(primary_key=True)
    asiento_id: Mapped[int] = mapped_column(ForeignKey("asientos.id", ondelete="CASCADE"))
    cuenta_codigo: Mapped[str] = mapped_column(ForeignKey("cuentas.codigo"), index=True)
    concepto: Mapped[str] = mapped_column(String(200), default="")
    debe: Mapped[int] = mapped_column(Integer, default=0)
    haber: Mapped[int] = mapped_column(Integer, default=0)

    asiento: Mapped[Asiento] = relationship(back_populates="apuntes")
    cuenta: Mapped[Cuenta] = relationship()


class Tercero(Base):
    __tablename__ = "terceros"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10))  # cliente | proveedor | ambos
    nif: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    direccion: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(100), default="")
    telefono: Mapped[str] = mapped_column(String(30), default="")
    # Subcuentas contables (430xxxx / 400xxxx), creadas al emitir/recibir la primera factura
    cuenta_cliente: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cuenta_proveedor: Mapped[str | None] = mapped_column(String(10), nullable=True)


class Factura(Base):
    __tablename__ = "facturas"
    __table_args__ = (UniqueConstraint("tipo", "numero", name="uq_factura_tipo_numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10), index=True)  # emitida | recibida
    numero: Mapped[str] = mapped_column(String(30))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    tercero_id: Mapped[int] = mapped_column(ForeignKey("terceros.id"))
    # Cuenta de ingreso (7xx) o de gasto/activo (6xx/2xx) contra la que se contabiliza
    cuenta_contrapartida: Mapped[str] = mapped_column(String(10))
    retencion_pct: Mapped[int] = mapped_column(Integer, default=0)  # 1500 = 15,00 %
    base_total: Mapped[int] = mapped_column(Integer)
    cuota_iva: Mapped[int] = mapped_column(Integer)
    retencion_importe: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(10), default="pendiente")  # pendiente | pagada
    asiento_id: Mapped[int | None] = mapped_column(ForeignKey("asientos.id"), nullable=True)
    asiento_pago_id: Mapped[int | None] = mapped_column(ForeignKey("asientos.id"), nullable=True)

    tercero: Mapped[Tercero] = relationship()
    lineas: Mapped[list["FacturaLinea"]] = relationship(
        back_populates="factura", cascade="all, delete-orphan", order_by="FacturaLinea.id"
    )


class FacturaLinea(Base):
    __tablename__ = "factura_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_id: Mapped[int] = mapped_column(ForeignKey("facturas.id", ondelete="CASCADE"))
    descripcion: Mapped[str] = mapped_column(String(200))
    base: Mapped[int] = mapped_column(Integer)
    tipo_iva: Mapped[int] = mapped_column(Integer)  # 2100 = 21,00 %
    cuota: Mapped[int] = mapped_column(Integer)

    factura: Mapped[Factura] = relationship(back_populates="lineas")


class Activo(Base):
    __tablename__ = "activos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    fecha_adquisicion: Mapped[date] = mapped_column(Date)
    valor: Mapped[int] = mapped_column(Integer)
    valor_residual: Mapped[int] = mapped_column(Integer, default=0)
    vida_util_anios: Mapped[int] = mapped_column(Integer)
    cuenta_activo: Mapped[str] = mapped_column(String(10), default="213")
    cuenta_amort_acum: Mapped[str] = mapped_column(String(10), default="281")
    cuenta_gasto: Mapped[str] = mapped_column(String(10), default="681")

    amortizaciones: Mapped[list["Amortizacion"]] = relationship(
        back_populates="activo", cascade="all, delete-orphan", order_by="Amortizacion.ejercicio"
    )


class Amortizacion(Base):
    __tablename__ = "amortizaciones"
    __table_args__ = (UniqueConstraint("activo_id", "ejercicio", name="uq_amortizacion_ejercicio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    activo_id: Mapped[int] = mapped_column(ForeignKey("activos.id", ondelete="CASCADE"))
    ejercicio: Mapped[int] = mapped_column(Integer)
    importe: Mapped[int] = mapped_column(Integer)
    asiento_id: Mapped[int | None] = mapped_column(ForeignKey("asientos.id"), nullable=True)

    activo: Mapped[Activo] = relationship(back_populates="amortizaciones")
