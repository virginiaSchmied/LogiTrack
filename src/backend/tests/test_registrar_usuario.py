"""
Tests para el endpoint POST /usuarios (registro de usuario por administrador).

Cubre los criterios de aceptación definidos en la historia de usuario:
  CA-1/CA-6 (NFR): contraseña no almacenada en texto plano (hash bcrypt)
  CA-2: registro exitoso con email, contraseña y rol válidos
  CA-3: email único — rechaza duplicados con 409
  CA-4: rol obligatorio
  CA-5: validación de campos obligatorios (email, contraseña, rol)
  CA-6: contraseña almacenada como hash
  CA-7: solo roles válidos del sistema son aceptados
  + control de acceso: solo ADMINISTRADOR puede registrar usuarios
"""
import pytest
from passlib.context import CryptContext

from tests.conftest import ROL_OPERADOR_UUID
import models

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

URL = "/usuarios"

_PAYLOAD_VALIDO = {
    "email":      "nuevo@logitrack.com",
    "password":   "Segura1234!",
    "rol_nombre": "OPERADOR",
}


# ── CA-2: Registro exitoso ────────────────────────────────────────────────────

def test_registro_exitoso(client, headers_admin):
    res = client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_admin)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "nuevo@logitrack.com"
    assert data["nombre_rol"] == "OPERADOR"
    assert data["estado"] == "ALTA"
    assert "uuid" in data
    assert "created_at" in data


# ── CA-1/CA-6: Contraseña almacenada como hash ────────────────────────────────

def test_contrasena_almacenada_como_hash(client, headers_admin, db_session):
    res = client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_admin)
    assert res.status_code == 201

    usuario = (
        db_session.query(models.Usuario)
        .filter(models.Usuario.email == "nuevo@logitrack.com")
        .first()
    )
    assert usuario is not None
    # La contraseña NO está en texto plano
    assert usuario.contrasena_hash != _PAYLOAD_VALIDO["password"]
    # El hash es verificable con bcrypt
    assert _pwd_ctx.verify(_PAYLOAD_VALIDO["password"], usuario.contrasena_hash)


def test_contrasena_incorrecta_no_verifica(client, headers_admin, db_session):
    """CA-6 + CA del sistema: hash incorrecto no autentica."""
    client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_admin)
    usuario = (
        db_session.query(models.Usuario)
        .filter(models.Usuario.email == "nuevo@logitrack.com")
        .first()
    )
    assert not _pwd_ctx.verify("ContraseñaIncorrecta!", usuario.contrasena_hash)


# ── CA-3: Email único ─────────────────────────────────────────────────────────

def test_email_duplicado_retorna_409(client, headers_admin):
    client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_admin)
    res = client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_admin)
    assert res.status_code == 409
    assert "email" in res.json()["detail"].lower()


def test_email_duplicado_case_insensitive(client, headers_admin):
    client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_admin)
    payload_upper = {**_PAYLOAD_VALIDO, "email": "NUEVO@LOGITRACK.COM"}
    res = client.post(URL, json=payload_upper, headers=headers_admin)
    assert res.status_code == 409


# ── CA-4: Rol obligatorio ─────────────────────────────────────────────────────

def test_sin_rol_retorna_422(client, headers_admin):
    payload = {"email": "x@test.com", "password": "Segura1234!"}
    res = client.post(URL, json=payload, headers=headers_admin)
    assert res.status_code == 422


# ── CA-5: Campos obligatorios ─────────────────────────────────────────────────

def test_sin_email_retorna_422(client, headers_admin):
    payload = {"password": "Segura1234!", "rol_nombre": "OPERADOR"}
    res = client.post(URL, json=payload, headers=headers_admin)
    assert res.status_code == 422


def test_sin_password_retorna_422(client, headers_admin):
    payload = {"email": "x@test.com", "rol_nombre": "OPERADOR"}
    res = client.post(URL, json=payload, headers=headers_admin)
    assert res.status_code == 422


def test_password_muy_corta_retorna_422(client, headers_admin):
    payload = {**_PAYLOAD_VALIDO, "password": "corta"}
    res = client.post(URL, json=payload, headers=headers_admin)
    assert res.status_code == 422


# ── CA-7: Solo roles válidos ──────────────────────────────────────────────────

@pytest.mark.parametrize("rol", ["OPERADOR", "SUPERVISOR", "ADMINISTRADOR"])
def test_roles_validos_aceptados(client, headers_admin, rol):
    payload = {**_PAYLOAD_VALIDO, "email": f"{rol.lower()}2@test.com", "rol_nombre": rol}
    res = client.post(URL, json=payload, headers=headers_admin)
    assert res.status_code == 201
    assert res.json()["nombre_rol"] == rol


def test_rol_invalido_retorna_422(client, headers_admin):
    payload = {**_PAYLOAD_VALIDO, "rol_nombre": "JEFE"}
    res = client.post(URL, json=payload, headers=headers_admin)
    assert res.status_code == 422


# ── Control de acceso: solo ADMINISTRADOR ────────────────────────────────────

def test_operador_no_puede_registrar_usuario(client, headers_operador):
    res = client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_operador)
    assert res.status_code == 403


def test_supervisor_no_puede_registrar_usuario(client, headers_supervisor):
    res = client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_supervisor)
    assert res.status_code == 403


def test_sin_autenticacion_retorna_403(client):
    res = client.post(URL, json=_PAYLOAD_VALIDO)
    assert res.status_code in (401, 403)


# ── Auditoría: EventoDeUsuario ALTA registrado ───────────────────────────────

def test_evento_alta_registrado(client, headers_admin, db_session):
    res = client.post(URL, json=_PAYLOAD_VALIDO, headers=headers_admin)
    assert res.status_code == 201

    import uuid as _uuid
    nuevo_uuid = _uuid.UUID(res.json()["uuid"])
    evento = (
        db_session.query(models.EventoDeUsuario)
        .filter(
            models.EventoDeUsuario.usuario_afectado_uuid == nuevo_uuid,
            models.EventoDeUsuario.accion == models.AccionUsuarioEnum.ALTA,
        )
        .first()
    )
    assert evento is not None
    assert evento.estado_final == models.EstadoUsuarioEnum.ALTA
    assert evento.estado_inicial is None
