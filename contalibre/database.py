import os
import shutil
from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Cada empresa tiene su propio fichero SQLite (mismo esquema que antes de
# multiempresa: aislamiento físico, no hace falta empresa_id en cada
# tabla ni riesgo de que una consulta olvide filtrar por empresa).
# Copia de seguridad = copiar el directorio de datos completo.
DATA_DIR = Path(os.environ.get("CONTALIBRE_DATA", "contalibre_data"))
EMPRESAS_DIR = DATA_DIR / "empresas"
CONTROL_DB_PATH = DATA_DIR / "control.db"

# Compatibilidad con instalaciones previas a multiempresa: si existe el
# fichero de una instalación antigua (CONTALIBRE_DB) y todavía no hay
# ninguna empresa registrada, se adopta como "Empresa 1" al arrancar.
LEGACY_DB_PATH = Path(os.environ.get("CONTALIBRE_DB", "contalibre.db"))


class Base(DeclarativeBase):
    """Modelos contables (una base de datos SQLite por empresa)."""


class ControlBase(DeclarativeBase):
    """Modelos de control: empresas, usuarios, membresías, sesiones."""


def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _crear_engine(ruta: Path) -> Engine:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{ruta}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragma)
    return engine


control_engine = _crear_engine(CONTROL_DB_PATH)
ControlSession = sessionmaker(bind=control_engine, autoflush=False, expire_on_commit=False)

_sessionmakers: dict[int, sessionmaker] = {}


def _sessionmaker_empresa(empresa_id: int) -> tuple[sessionmaker, bool]:
    """Devuelve el sessionmaker de la empresa, creando su base si es nueva."""
    if empresa_id in _sessionmakers:
        return _sessionmakers[empresa_id], False
    EMPRESAS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = EMPRESAS_DIR / f"{empresa_id}.db"
    nueva = not ruta.exists()
    engine = _crear_engine(ruta)
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    _sessionmakers[empresa_id] = fabrica
    return fabrica, nueva


def _cargar_pgc_si_vacio(db: Session) -> None:
    from . import models
    from .pgc import PGC_CUENTAS

    if db.scalar(select(models.Cuenta.codigo).limit(1)) is None:
        for codigo, nombre in PGC_CUENTAS:
            db.add(models.Cuenta(codigo=codigo, nombre=nombre))
        db.commit()


def sesion_empresa(empresa_id: int) -> Session:
    """Sesión ligada a la base de datos de una empresa concreta.

    La primera vez que se accede a una empresa se crean sus tablas y se
    precarga el Plan General Contable.
    """
    fabrica, nueva = _sessionmaker_empresa(empresa_id)
    db = fabrica()
    if nueva:
        _cargar_pgc_si_vacio(db)
    return db


def get_control_db():
    db = ControlSession()
    try:
        yield db
    finally:
        db.close()


def init_control_db() -> None:
    """Crea las tablas de control y migra una instalación antigua si procede."""
    from . import models_control  # noqa: F401

    ControlBase.metadata.create_all(control_engine)
    _migrar_instalacion_antigua()


def reset_para_pruebas(data_dir: Path) -> None:
    """Reinicia el estado de conexión global apuntando a un directorio
    nuevo. Solo lo usan los tests, para aislar cada caso entre sí."""
    global DATA_DIR, EMPRESAS_DIR, CONTROL_DB_PATH, LEGACY_DB_PATH, control_engine
    DATA_DIR = data_dir
    EMPRESAS_DIR = DATA_DIR / "empresas"
    CONTROL_DB_PATH = DATA_DIR / "control.db"
    LEGACY_DB_PATH = DATA_DIR / "no-existe-legacy.db"
    control_engine = _crear_engine(CONTROL_DB_PATH)
    ControlSession.configure(bind=control_engine)
    _sessionmakers.clear()


def _migrar_instalacion_antigua() -> None:
    from . import models_control

    if not LEGACY_DB_PATH.exists():
        return
    with ControlSession() as db:
        if db.scalar(select(models_control.Empresa.id).limit(1)) is not None:
            return  # ya hay empresas: instalación nueva o ya migrada
        EMPRESAS_DIR.mkdir(parents=True, exist_ok=True)
        destino = EMPRESAS_DIR / "1.db"
        if not destino.exists():
            shutil.copy2(LEGACY_DB_PATH, destino)
        db.add(models_control.Empresa(id=1, nombre="Empresa migrada"))
        db.commit()
