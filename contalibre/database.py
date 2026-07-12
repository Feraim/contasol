import os
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_PATH = Path(os.environ.get("CONTALIBRE_DB", "contalibre.db"))

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crea las tablas y carga el Plan General Contable si la base está vacía."""
    from . import models  # noqa: F401  (registra los modelos en Base)
    from .pgc import PGC_CUENTAS

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(models.Cuenta.codigo).limit(1)) is None:
            for codigo, nombre in PGC_CUENTAS:
                db.add(models.Cuenta(codigo=codigo, nombre=nombre))
            db.commit()
