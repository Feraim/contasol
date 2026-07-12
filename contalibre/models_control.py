from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import ControlBase as Base


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    nif: Mapped[str] = mapped_column(String(20), default="")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    nombre: Mapped[str] = mapped_column(String(150), default="")


class Membresia(Base):
    """Pertenencia de un usuario a una empresa, con su rol."""

    __tablename__ = "membresias"
    __table_args__ = (UniqueConstraint("usuario_id", "empresa_id", name="uq_membresia_usuario_empresa"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"), index=True)
    rol: Mapped[str] = mapped_column(String(20), default="admin")  # admin | editor

    usuario: Mapped[Usuario] = relationship()
    empresa: Mapped[Empresa] = relationship()


class Sesion(Base):
    __tablename__ = "sesiones"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    creada: Mapped[datetime] = mapped_column(DateTime)
