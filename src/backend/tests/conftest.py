import os
import uuid

# Debe setearse antes de cualquier import del backend para que database.py
# no intente conectarse a la DB de producción durante los tests.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 — necesario para registrar las tablas en Base.metadata
from database import Base, get_db
from main import app
from models import Usuario, Rol, EstadoUsuarioEnum
from auth import hash_password

# StaticPool fuerza que todas las conexiones compartan la misma DB en memoria.
# Sin esto, create_all y la app usan conexiones distintas (cada una vacía).
_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)


def _override_get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


def _create_user_and_login(client, email: str, password: str, rol_nombre: str) -> dict:
    """Crea un usuario directamente en la DB y devuelve los headers de autenticación."""
    db = _SessionLocal()
    try:
        rol = db.query(Rol).filter(Rol.nombre == rol_nombre).first()
        if not rol:
            rol = Rol(uuid=uuid.uuid4(), nombre=rol_nombre)
            db.add(rol)
            db.flush()

        usuario = Usuario(
            uuid=uuid.uuid4(),
            email=email,
            contrasena_hash=hash_password(password),
            estado=EstadoUsuarioEnum.ALTA,
            rol_uuid=rol.uuid,
        )
        db.add(usuario)
        db.commit()
    finally:
        db.close()

    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login falló para {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client():
    """TestClient con base de datos SQLite en memoria, reseteada entre tests."""
    Base.metadata.create_all(bind=_ENGINE)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=_ENGINE)


@pytest.fixture()
def db_session(client):
    """Sesión directa a la DB de prueba para setup y assertions que requieren acceso al ORM."""
    db = _SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def headers_operador(client):
    """Headers JWT para un usuario con rol OPERADOR."""
    return _create_user_and_login(client, "operador@test.com", "password123", "OPERADOR")


@pytest.fixture()
def headers_supervisor(client):
    """Headers JWT para un usuario con rol SUPERVISOR."""
    return _create_user_and_login(client, "supervisor@test.com", "password123", "SUPERVISOR")


@pytest.fixture()
def headers_admin(client):
    """Headers JWT para un usuario con rol ADMINISTRADOR."""
    return _create_user_and_login(client, "admin@test.com", "password123", "ADMINISTRADOR")