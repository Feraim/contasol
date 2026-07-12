from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models_control
from ..database import get_control_db
from ..deps import usuario_actual
from ..services import backup as svc_backup

router = APIRouter(prefix="/empresas", tags=["empresas"])


class EmpresaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    nif: str = ""


class InvitarIn(BaseModel):
    email: str
    rol: str = Field(default="editor", pattern="^(admin|editor)$")


def _rol_en_empresa(db: Session, usuario_id: int, empresa_id: int) -> str | None:
    m = db.scalar(
        select(models_control.Membresia).where(
            models_control.Membresia.usuario_id == usuario_id,
            models_control.Membresia.empresa_id == empresa_id,
        )
    )
    return m.rol if m else None


@router.get("")
def mis_empresas(
    usuario: models_control.Usuario = Depends(usuario_actual), db: Session = Depends(get_control_db)
):
    membresias = db.scalars(
        select(models_control.Membresia).where(models_control.Membresia.usuario_id == usuario.id)
    ).all()
    return [
        {"id": m.empresa_id, "nombre": db.get(models_control.Empresa, m.empresa_id).nombre, "rol": m.rol}
        for m in membresias
    ]


@router.post("", status_code=201)
def crear_empresa(
    datos: EmpresaIn,
    usuario: models_control.Usuario = Depends(usuario_actual),
    db: Session = Depends(get_control_db),
):
    empresa = models_control.Empresa(nombre=datos.nombre, nif=datos.nif)
    db.add(empresa)
    db.flush()
    db.add(models_control.Membresia(usuario_id=usuario.id, empresa_id=empresa.id, rol="admin"))
    db.commit()
    return {"id": empresa.id, "nombre": empresa.nombre, "rol": "admin"}


@router.get("/{empresa_id}/exportar")
def exportar_empresa(
    empresa_id: int,
    usuario: models_control.Usuario = Depends(usuario_actual),
    db: Session = Depends(get_control_db),
):
    if _rol_en_empresa(db, usuario.id, empresa_id) != "admin":
        raise HTTPException(403, "Solo un administrador puede exportar la copia de seguridad")
    contenido = svc_backup.exportar_zip(empresa_id)
    return Response(
        contenido,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="contalibre_empresa_{empresa_id}.zip"'},
    )


@router.get("/{empresa_id}/usuarios")
def listar_usuarios(
    empresa_id: int,
    usuario: models_control.Usuario = Depends(usuario_actual),
    db: Session = Depends(get_control_db),
):
    if _rol_en_empresa(db, usuario.id, empresa_id) is None:
        raise HTTPException(403, "No perteneces a esa empresa")
    membresias = db.scalars(
        select(models_control.Membresia).where(models_control.Membresia.empresa_id == empresa_id)
    ).all()
    return [
        {"usuario_id": m.usuario_id, "email": db.get(models_control.Usuario, m.usuario_id).email, "rol": m.rol}
        for m in membresias
    ]


@router.post("/{empresa_id}/usuarios", status_code=201)
def invitar_usuario(
    empresa_id: int,
    datos: InvitarIn,
    usuario: models_control.Usuario = Depends(usuario_actual),
    db: Session = Depends(get_control_db),
):
    if _rol_en_empresa(db, usuario.id, empresa_id) != "admin":
        raise HTTPException(403, "Solo un administrador puede añadir usuarios")
    objetivo = db.scalar(select(models_control.Usuario).where(models_control.Usuario.email == datos.email))
    if objetivo is None:
        raise HTTPException(404, "No existe ningún usuario registrado con ese email")
    if _rol_en_empresa(db, objetivo.id, empresa_id) is not None:
        raise HTTPException(409, "Ese usuario ya pertenece a la empresa")
    db.add(models_control.Membresia(usuario_id=objetivo.id, empresa_id=empresa_id, rol=datos.rol))
    db.commit()
    return {"usuario_id": objetivo.id, "email": objetivo.email, "rol": datos.rol}


@router.delete("/{empresa_id}/usuarios/{usuario_id}", status_code=204)
def quitar_usuario(
    empresa_id: int,
    usuario_id: int,
    usuario: models_control.Usuario = Depends(usuario_actual),
    db: Session = Depends(get_control_db),
):
    if _rol_en_empresa(db, usuario.id, empresa_id) != "admin":
        raise HTTPException(403, "Solo un administrador puede quitar usuarios")
    if usuario_id == usuario.id:
        raise HTTPException(409, "No puedes quitarte a ti mismo de la empresa")
    m = db.scalar(
        select(models_control.Membresia).where(
            models_control.Membresia.usuario_id == usuario_id,
            models_control.Membresia.empresa_id == empresa_id,
        )
    )
    if m is None:
        raise HTTPException(404, "Ese usuario no pertenece a la empresa")
    db.delete(m)
    db.commit()
