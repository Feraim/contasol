import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import auth, models_control, ratelimit
from ..auth import DURACION_RESET_PASSWORD, DURACION_SESION
from ..database import get_control_db
from ..deps import COOKIE_SESION, usuario_actual

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger("contalibre.auth")


class RegistroIn(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=8, max_length=200)
    nombre: str = ""
    empresa_nombre: str = Field(min_length=1, max_length=150)


class LoginIn(BaseModel):
    email: str
    password: str


class OlvidePasswordIn(BaseModel):
    email: str


class RestablecerPasswordIn(BaseModel):
    token: str
    password_nueva: str = Field(min_length=8, max_length=200)


class CambiarPasswordIn(BaseModel):
    password_actual: str
    password_nueva: str = Field(min_length=8, max_length=200)


def _crear_sesion(db: Session, response: Response, usuario_id: int) -> None:
    token = auth.generar_token()
    db.add(models_control.Sesion(token=token, usuario_id=usuario_id, creada=datetime.now(timezone.utc)))
    db.commit()
    response.set_cookie(
        COOKIE_SESION, token, httponly=True, samesite="lax",
        max_age=int(DURACION_SESION.total_seconds()),
    )


def _invalidar_sesiones(db: Session, usuario_id: int) -> None:
    """Cierra todas las sesiones activas de un usuario (tras cambiar la contraseña)."""
    db.execute(delete(models_control.Sesion).where(models_control.Sesion.usuario_id == usuario_id))


def _perfil(db: Session, usuario: models_control.Usuario) -> dict:
    membresias = db.scalars(
        select(models_control.Membresia).where(models_control.Membresia.usuario_id == usuario.id)
    ).all()
    empresas = [
        {"id": m.empresa_id, "nombre": db.get(models_control.Empresa, m.empresa_id).nombre, "rol": m.rol}
        for m in membresias
    ]
    return {"id": usuario.id, "email": usuario.email, "nombre": usuario.nombre, "empresas": empresas}


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


@router.post("/login")
def login(datos: LoginIn, response: Response, db: Session = Depends(get_control_db)):
    clave = datos.email.strip().lower()
    if ratelimit.bloqueado(clave):
        raise HTTPException(429, "Demasiados intentos fallidos; espera unos minutos y vuelve a intentarlo")
    usuario = db.scalar(select(models_control.Usuario).where(models_control.Usuario.email == datos.email))
    if usuario is None or not auth.verificar_password(datos.password, usuario.password_hash):
        ratelimit.registrar_fallo(clave)
        raise HTTPException(401, "Email o contraseña incorrectos")
    ratelimit.limpiar(clave)
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


@router.post("/olvide-password", status_code=202)
def olvide_password(datos: OlvidePasswordIn, db: Session = Depends(get_control_db)):
    """Genera un token de restablecimiento. Como esta aplicación es local y no
    tiene infraestructura de correo, el token se registra en la consola del
    servidor (solo quien tiene acceso a la máquina puede leerlo)."""
    usuario = db.scalar(select(models_control.Usuario).where(models_control.Usuario.email == datos.email))
    if usuario is not None:
        token = auth.generar_token()
        db.add(
            models_control.RestablecimientoPassword(
                token=token, usuario_id=usuario.id, creado=datetime.now(timezone.utc)
            )
        )
        db.commit()
        logger.warning(
            "Restablecimiento de contraseña solicitado para %s — token: %s (válido 1 hora)",
            usuario.email, token,
        )
    # Respuesta siempre genérica: no revela si el email existe o no.
    return {
        "mensaje": "Si el email existe, se ha generado un token de restablecimiento "
        "(consulta la consola donde se ejecuta el servidor)."
    }


@router.post("/restablecer-password", status_code=204)
def restablecer_password(datos: RestablecerPasswordIn, db: Session = Depends(get_control_db)):
    reset = db.get(models_control.RestablecimientoPassword, datos.token)
    if reset is None:
        raise HTTPException(400, "Token inválido o ya utilizado")
    creado = reset.creado if reset.creado.tzinfo else reset.creado.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - creado > DURACION_RESET_PASSWORD:
        db.delete(reset)
        db.commit()
        raise HTTPException(400, "El token ha caducado; solicita uno nuevo")
    usuario = db.get(models_control.Usuario, reset.usuario_id)
    usuario.password_hash = auth.hash_password(datos.password_nueva)
    db.delete(reset)
    _invalidar_sesiones(db, usuario.id)
    db.commit()


@router.put("/password", status_code=204)
def cambiar_password(
    datos: CambiarPasswordIn,
    usuario: models_control.Usuario = Depends(usuario_actual),
    db: Session = Depends(get_control_db),
):
    if not auth.verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(401, "La contraseña actual no es correcta")
    usuario.password_hash = auth.hash_password(datos.password_nueva)
    db.commit()
