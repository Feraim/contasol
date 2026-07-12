from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auth, models_control
from ..database import get_control_db
from ..deps import COOKIE_SESION, usuario_actual

router = APIRouter(prefix="/auth", tags=["auth"])

DURACION_SESION = timedelta(days=30)


class RegistroIn(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=8, max_length=200)
    nombre: str = ""
    empresa_nombre: str = Field(min_length=1, max_length=150)


class LoginIn(BaseModel):
    email: str
    password: str


def _crear_sesion(db: Session, response: Response, usuario_id: int) -> None:
    token = auth.generar_token()
    db.add(models_control.Sesion(token=token, usuario_id=usuario_id, creada=datetime.now(timezone.utc)))
    db.commit()
    response.set_cookie(
        COOKIE_SESION, token, httponly=True, samesite="lax",
        max_age=int(DURACION_SESION.total_seconds()),
    )


def _perfil(db: Session, usuario: models_control.Usuario) -> dict:
    membresias = db.scalars(
        select(models_control.Membresia).where(models_control.Membresia.usuario_id == usuario.id)
    ).all()
    empresas = [
        {"id": m.empresa_id, "nombre": db.get(models_control.Empresa, m.empresa_id).nombre, "rol": m.rol}
        for m in membresias
    ]
    return {"id": usuario.id, "email": usuario.email, "nombre": usuario.nombre, "empresas": empresas}


@router.post("/registro", status_code=201)
def registro(datos: RegistroIn, response: Response, db: Session = Depends(get_control_db)):
    if db.scalar(select(models_control.Usuario.id).where(models_control.Usuario.email == datos.email)):
        raise HTTPException(409, "Ya existe un usuario con ese email")
    usuario = models_control.Usuario(
        email=datos.email, password_hash=auth.hash_password(datos.password), nombre=datos.nombre,
    )
    db.add(usuario)
    db.flush()
    empresa = models_control.Empresa(nombre=datos.empresa_nombre)
    db.add(empresa)
    db.flush()
    db.add(models_control.Membresia(usuario_id=usuario.id, empresa_id=empresa.id, rol="admin"))
    db.flush()
    _reclamar_empresas_huerfanas(db, usuario.id)
    db.commit()
    _crear_sesion(db, response, usuario.id)
    return _perfil(db, usuario)


def _reclamar_empresas_huerfanas(db: Session, usuario_id: int) -> None:
    """El primer usuario en registrarse se convierte en admin de
    cualquier empresa sin usuarios (p. ej. una migrada de una
    instalación previa a multiempresa, que no tiene a nadie vinculado)."""
    huerfanas = db.scalars(
        select(models_control.Empresa).where(
            models_control.Empresa.id.not_in(select(models_control.Membresia.empresa_id))
        )
    ).all()
    for empresa in huerfanas:
        db.add(models_control.Membresia(usuario_id=usuario_id, empresa_id=empresa.id, rol="admin"))


@router.post("/login")
def login(datos: LoginIn, response: Response, db: Session = Depends(get_control_db)):
    usuario = db.scalar(select(models_control.Usuario).where(models_control.Usuario.email == datos.email))
    if usuario is None or not auth.verificar_password(datos.password, usuario.password_hash):
        raise HTTPException(401, "Email o contraseña incorrectos")
    _crear_sesion(db, response, usuario.id)
    return _perfil(db, usuario)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    contalibre_sesion: str | None = Cookie(default=None, alias=COOKIE_SESION),
    db: Session = Depends(get_control_db),
):
    if contalibre_sesion:
        sesion = db.get(models_control.Sesion, contalibre_sesion)
        if sesion is not None:
            db.delete(sesion)
            db.commit()
    response.delete_cookie(COOKIE_SESION)


@router.get("/me")
def me(usuario: models_control.Usuario = Depends(usuario_actual), db: Session = Depends(get_control_db)):
    return _perfil(db, usuario)
