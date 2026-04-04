"""
Endpoints de autenticación: login y logout.

Cubre LP-21 (login), LP-99 (logout), LP-254 (JWT), LP-107 (registro de eventos de usuario).
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, EstadoUsuarioEnum, EventoDeUsuario, AccionUsuarioEnum
from schemas import LoginRequest, TokenResponse
from auth import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Autentica al usuario con email y contraseña.
    Devuelve un JWT firmado con uuid, email, rol, iat y exp (8 hs). LP-21 / LP-254.
    Registra un EventoDeUsuario LOGIN para auditoría. LP-107.
    """
    # Mensaje genérico para no revelar qué campo es incorrecto (LP-21 CA-3)
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales incorrectas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = (
        db.query(Usuario)
        .filter(func.lower(Usuario.email) == payload.email.strip().lower())
        .first()
    )

    if not user:
        raise credenciales_invalidas

    # Usuario inactivo tratado igual que credenciales incorrectas (LP-21 CA-3)
    if user.estado != EstadoUsuarioEnum.ALTA:
        raise credenciales_invalidas

    if not verify_password(payload.password, user.contrasena_hash):
        raise credenciales_invalidas

    token = create_access_token(
        sub=str(user.uuid),
        email=user.email,
        rol=user.rol.nombre,
    )

    # Registrar evento LOGIN (LP-107)
    evento = EventoDeUsuario(
        uuid=uuid.uuid4(),
        accion=AccionUsuarioEnum.LOGIN,
        estado_inicial=user.estado,
        estado_final=user.estado,
        usuario_ejecutor_uuid=user.uuid,
        usuario_afectado_uuid=user.uuid,
    )
    db.add(evento)
    db.commit()

    return TokenResponse(
        access_token=token,
        email=user.email,
        nombre_rol=user.rol.nombre,
    )


@router.post("/logout", status_code=200)
def logout(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cierra la sesión del usuario autenticado.
    El token se invalida en el cliente (localStorage). LP-99 / LP-254.
    No implementa blacklist de tokens en el MVP (LP-254 decisión de diseño).
    Registra un EventoDeUsuario LOGOUT. LP-107.
    """
    evento = EventoDeUsuario(
        uuid=uuid.uuid4(),
        accion=AccionUsuarioEnum.LOGOUT,
        estado_inicial=current_user.estado,
        estado_final=current_user.estado,
        usuario_ejecutor_uuid=current_user.uuid,
        usuario_afectado_uuid=current_user.uuid,
    )
    db.add(evento)
    db.commit()

    return {"message": "Sesión cerrada correctamente"}
