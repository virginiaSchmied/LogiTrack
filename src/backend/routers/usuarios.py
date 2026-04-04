"""
Endpoints de gestión de usuarios (solo ADMINISTRADOR).

Cubre el registro de nuevos usuarios con contraseña hasheada (bcrypt),
validación de email único, rol obligatorio y auditoría mediante EventoDeUsuario.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, Rol, EstadoUsuarioEnum, EventoDeUsuario, AccionUsuarioEnum
from schemas import UsuarioCreate, UsuarioOut
from auth import hash_password, require_admin

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(
    payload: UsuarioCreate,
    current_user: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Registra un nuevo usuario en el sistema.

    - Solo accesible para ADMINISTRADOR.
    - La contraseña se almacena como hash bcrypt (CA-1/CA-6).
    - Rechaza emails ya registrados (CA-3).
    - Solo acepta roles válidos del sistema (CA-7).
    - Registra un EventoDeUsuario ALTA para auditoría.
    """
    # CA-3: email único (case-insensitive)
    existente = (
        db.query(Usuario)
        .filter(func.lower(Usuario.email) == payload.email)
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado en el sistema",
        )

    # CA-7: el rol debe existir en la base de datos
    rol = db.query(Rol).filter(Rol.nombre == payload.rol_nombre).first()
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El rol especificado no existe en el sistema",
        )

    # CA-1/CA-6: contraseña hasheada con bcrypt
    nuevo_usuario = Usuario(
        uuid=uuid.uuid4(),
        email=payload.email,
        contrasena_hash=hash_password(payload.password),
        estado=EstadoUsuarioEnum.ALTA,
        rol_uuid=rol.uuid,
    )
    db.add(nuevo_usuario)
    db.flush()

    # Auditoría: registrar evento ALTA
    evento = EventoDeUsuario(
        uuid=uuid.uuid4(),
        accion=AccionUsuarioEnum.ALTA,
        estado_inicial=None,
        estado_final=EstadoUsuarioEnum.ALTA,
        usuario_ejecutor_uuid=current_user.uuid,
        usuario_afectado_uuid=nuevo_usuario.uuid,
    )
    db.add(evento)
    db.commit()
    db.refresh(nuevo_usuario)

    return UsuarioOut(
        uuid=nuevo_usuario.uuid,
        email=nuevo_usuario.email,
        nombre_rol=nuevo_usuario.rol.nombre,
        estado=nuevo_usuario.estado,
        created_at=nuevo_usuario.created_at,
    )
