import os

# Debe setearse antes de cualquier import del backend para que database.py
# no intente conectarse a la DB de producción durante los tests.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 — necesario para registrar las tablas en Base.metadata
from database import Base, get_db
from main import app
from auth import hash_password, create_access_token

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

# ── UUIDs fijos para los tests ────────────────────────────────────────────────

ROL_OPERADOR_UUID   = uuid.UUID("11111111-0001-0001-0001-000000000001")
ROL_SUPERVISOR_UUID = uuid.UUID("11111111-0001-0001-0001-000000000002")
ROL_ADMIN_UUID      = uuid.UUID("11111111-0001-0001-0001-000000000003")

USUARIO_OPERADOR_UUID   = uuid.UUID("22222222-0002-0002-0002-000000000001")
USUARIO_SUPERVISOR_UUID = uuid.UUID("22222222-0002-0002-0002-000000000002")
USUARIO_ADMIN_UUID      = uuid.UUID("22222222-0002-0002-0002-000000000003")


def _seed_db(db):
    """Inserta los roles y usuarios mínimos requeridos por los tests."""
    roles = [
        models.Rol(uuid=ROL_OPERADOR_UUID,   nombre="OPERADOR"),
        models.Rol(uuid=ROL_SUPERVISOR_UUID, nombre="SUPERVISOR"),
        models.Rol(uuid=ROL_ADMIN_UUID,      nombre="ADMINISTRADOR"),
    ]
    db.add_all(roles)
    db.flush()

    users = [
        models.Usuario(
            uuid=USUARIO_OPERADOR_UUID,
            email="operador@test.com",
            contrasena_hash=hash_password("test1234"),
            estado=models.EstadoUsuarioEnum.ALTA,
            rol_uuid=ROL_OPERADOR_UUID,
        ),
        models.Usuario(
            uuid=USUARIO_SUPERVISOR_UUID,
            email="supervisor@test.com",
            contrasena_hash=hash_password("test1234"),
            estado=models.EstadoUsuarioEnum.ALTA,
            rol_uuid=ROL_SUPERVISOR_UUID,
        ),
        models.Usuario(
            uuid=USUARIO_ADMIN_UUID,
            email="admin@test.com",
            contrasena_hash=hash_password("test1234"),
            estado=models.EstadoUsuarioEnum.ALTA,
            rol_uuid=ROL_ADMIN_UUID,
        ),
    ]
    db.add_all(users)
    db.commit()


def _make_token(user_uuid: uuid.UUID, email: str, rol: str) -> str:
    return create_access_token(sub=str(user_uuid), email=email, rol=rol)

_current_sessionlocal = None

@pytest.fixture()
def client():
    """TestClient con BD SQLite nueva PARA CADA TEST."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    Base.metadata.create_all(bind=engine)

    db = _current_sessionlocal()
    try:
        _seed_db(db)
    finally:
        db.close()

    with TestClient(app) as c:
        yield c

    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(client):
    """Acceso directo al ORM para setup/assertions."""
    global _current_sessionlocal

    db = _current_sessionlocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def headers_operador():
    """Headers HTTP con JWT de rol Operador."""
    token = _make_token(USUARIO_OPERADOR_UUID, "operador@test.com", "OPERADOR")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers_supervisor():
    """Headers HTTP con JWT de rol Supervisor."""
    token = _make_token(USUARIO_SUPERVISOR_UUID, "supervisor@test.com", "SUPERVISOR")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers_admin():
    """Headers HTTP con JWT de rol Administrador."""
    token = _make_token(USUARIO_ADMIN_UUID, "admin@test.com", "ADMINISTRADOR")
    return {"Authorization": f"Bearer {token}"}
