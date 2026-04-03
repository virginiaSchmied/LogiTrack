"""
Utilidades de autenticación y autorización JWT.

Cubre LP-254 (mecanismo JWT centralizado).
"""
import os
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario, EstadoUsuarioEnum

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "8"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


# ── Contraseñas ───────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(sub: str, email: str, rol: str) -> str:
    """
    Genera un JWT firmado con HS256.
    Payload: sub (uuid), email, rol, iat, exp.
    Expiración configurable vía JWT_EXPIRATION_HOURS (default 8h). LP-254 CA-1/CA-2.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "sub": sub,
        "email": email,
        "rol": rol,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodifica y valida la firma y expiración del token.
    Lanza 401 si el token es inválido o expirado. LP-254 CA-5/CA-6.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── Dependencias FastAPI ──────────────────────────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Dependencia que extrae y valida el token del header Authorization.
    Retorna el Usuario activo. LP-254 CA-4/CA-8.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    user_uuid_str = payload.get("sub")
    if not user_uuid_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    try:
        user_uuid = _uuid.UUID(user_uuid_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    user = (
        db.query(Usuario)
        .filter(Usuario.uuid == user_uuid, Usuario.estado == EstadoUsuarioEnum.ALTA)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo",
        )
    return user


class _RequireRoles:
    """
    Dependencia de autorización por rol.
    Lanza 403 si el rol del usuario no está en el conjunto permitido. LP-254 CA-7.
    """

    def __init__(self, *roles: str) -> None:
        self.roles = set(roles)

    def __call__(self, current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol.nombre not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: permisos insuficientes",
            )
        return current_user


# Instancias reutilizables — FastAPI las cachea correctamente por identidad de objeto
require_operador_supervisor = _RequireRoles("OPERADOR", "SUPERVISOR")
require_supervisor          = _RequireRoles("SUPERVISOR")
require_admin               = _RequireRoles("ADMINISTRADOR")
