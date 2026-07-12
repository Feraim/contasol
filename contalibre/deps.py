from datetime import datetime, timezone

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models_control
from .auth import DURACION_SESION
from .database import get_control_db, sesion_empresa

COOKIE_SESION = "contalibre_sesion"


def usuario_actual(
    contalibre_sesion: str | None = Cookie(default=None, alias=COOKIE_SESION),
    db: Session = Depends(get_control_db),
) -> models_control.Usuario:
    if not contalibre_sesion:
        raise HTTPException(401, "No has iniciado sesión")
    sesion = db.get(models_control.Sesion, contalibre_sesion)
    if sesion is None:
        raise HTTPException(401, "Sesión no válida o caducada")
    creada = sesion.creada if sesion.creada.tzinfo else sesion.creada.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - creada > DURACION_SESION:
        db.delete(sesion)
        db.commit()
        raise HTTPException(401, "Sesión caducada, vuelve a iniciar sesión")
    usuario = db.get(models_control.Usuario, sesion.usuario_id)
    if usuario is None:
        raise HTTPException(401, "Sesión no válida")
    return usuario


def membresias_actual(
    usuario: models_control.Usuario = Depends(usuario_actual),
    db: Session = Depends(get_control_db),
) -> list[models_control.Membresia]:
    return list(
        db.scalars(
            select(models_control.Membresia).where(models_control.Membresia.usuario_id == usuario.id)
        )
    )


def empresa_actual_id(
    x_empresa_id: int | None = Header(default=None, alias="X-Empresa-Id"),
    membresias: list[models_control.Membresia] = Depends(membresias_actual),
) -> int:
    if not membresias:
        raise HTTPException(403, "El usuario no pertenece a ninguna empresa")
    if x_empresa_id is not None:
        if not any(m.empresa_id == x_empresa_id for m in membresias):
            raise HTTPException(403, "No perteneces a esa empresa")
        return x_empresa_id
    return membresias[0].empresa_id


def rol_actual(
    empresa_id: int = Depends(empresa_actual_id),
    membresias: list[models_control.Membresia] = Depends(membresias_actual),
) -> str:
    return next(m.rol for m in membresias if m.empresa_id == empresa_id)


def requiere_admin(rol: str = Depends(rol_actual)) -> None:
    if rol != "admin":
        raise HTTPException(403, "Solo un administrador de la empresa puede hacer esto")


def get_db(empresa_id: int = Depends(empresa_actual_id)):
    db = sesion_empresa(empresa_id)
    try:
        yield db
    finally:
        db.close()
