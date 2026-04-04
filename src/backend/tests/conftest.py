import os

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
import scheduler as _sched_module

# El lifespan de FastAPI llama a scheduler.start() y scheduler.shutdown().
# shutdown() elimina el jobstore en memoria, con lo que los jobs se pierden
# y los tests de configuración del scheduler (CP-0331) fallan.
# Mockeamos start/shutdown para que sean no-ops durante toda la sesión de tests.
# Los tests de recalcular_prioridades() llaman a la función directamente,
# por lo que no necesitan que el scheduler esté corriendo.
_sched_module.scheduler.start = lambda: None
_sched_module.scheduler.shutdown = lambda wait=True: None

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
