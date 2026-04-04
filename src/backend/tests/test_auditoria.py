"""
Tests unitarios para el historial de acciones de usuarios (auditoría).

Historia: Como administrador autenticado, quiero consultar y filtrar el historial
de acciones realizadas sobre usuarios del sistema para poder auditar la actividad
de un usuario específico dentro del sistema.

Tabla: EventoDeUsuario — acciones ALTA, BAJA, LOGIN, LOGOUT.
Solo el Administrador puede acceder. Los registros son de solo lectura.

Criterios de Aceptación cubiertos:
  CA-1 — Acceso exclusivo del Administrador (403 para Operador y Supervisor)
  CA-2 — Consulta exitosa sin filtro (devuelve todos los eventos, más reciente primero)
  CA-3 — Filtrado por UUID de usuario afectado
  CA-4 — Filtrado por UUID de usuario ejecutor
  CA-5 — UUID sin resultados devuelve mensaje claro (lista vacía)
  CA-6 — Datos mínimos requeridos por entrada
  CA-7 — Historial incluye todos los tipos de acciones (ALTA, LOGIN, LOGOUT, BAJA)
  CA-8 — Registros de solo lectura (no existe endpoint de modificación/eliminación)
"""
import uuid as _uuid

import pytest

from models import (
    EventoDeUsuario,
    AccionUsuarioEnum,
    EstadoUsuarioEnum,
    Usuario,
    Rol,
)
from auth import hash_password

_ENDPOINT = "/auditoria/eventos"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _nuevo_usuario(db, rol_nombre: str, email: str) -> Usuario:
    """Crea (o reutiliza) un rol y crea un usuario en la DB de prueba."""
    rol = db.query(Rol).filter(Rol.nombre == rol_nombre).first()
    if not rol:
        rol = Rol(uuid=_uuid.uuid4(), nombre=rol_nombre)
        db.add(rol)
        db.flush()

    usuario = Usuario(
        uuid=_uuid.uuid4(),
        email=email,
        contrasena_hash=hash_password("password123"),
        estado=EstadoUsuarioEnum.ALTA,
        rol_uuid=rol.uuid,
    )
    db.add(usuario)
    db.flush()
    return usuario


def _evento(db, accion: AccionUsuarioEnum, ejecutor: Usuario, afectado: Usuario,
            estado_inicial=None, estado_final=EstadoUsuarioEnum.ALTA) -> EventoDeUsuario:
    """Inserta un EventoDeUsuario en la DB de prueba."""
    ev = EventoDeUsuario(
        uuid=_uuid.uuid4(),
        accion=accion,
        estado_inicial=estado_inicial,
        estado_final=estado_final,
        usuario_ejecutor_uuid=ejecutor.uuid,
        usuario_afectado_uuid=afectado.uuid,
    )
    db.add(ev)
    db.flush()
    return ev


# ── CA-1: Acceso exclusivo del Administrador ──────────────────────────────────

def test_ca1_sin_token_retorna_401(client):
    """Sin token de autenticación el endpoint retorna 401."""
    assert client.get(_ENDPOINT).status_code == 401


def test_ca1_operador_retorna_403(client, headers_operador):
    """Un Operador autenticado recibe 403 al intentar acceder al historial."""
    assert client.get(_ENDPOINT, headers=headers_operador).status_code == 403


def test_ca1_supervisor_retorna_403(client, headers_supervisor):
    """Un Supervisor autenticado recibe 403 al intentar acceder al historial."""
    assert client.get(_ENDPOINT, headers=headers_supervisor).status_code == 403


def test_ca1_administrador_puede_acceder(client, headers_admin):
    """El Administrador autenticado puede acceder al historial (200 OK)."""
    resp = client.get(_ENDPOINT, headers=headers_admin)
    assert resp.status_code == 200


# ── CA-2: Consulta exitosa sin filtro ────────────────────────────────────────

def test_ca2_sin_filtro_devuelve_lista_completa(client, headers_admin, db_session):
    """Sin filtros se devuelve la lista completa de EventoDeUsuario."""
    admin = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin2@test.com")
    user  = _nuevo_usuario(db_session, "OPERADOR", "op2@test.com")
    _evento(db_session, AccionUsuarioEnum.ALTA, admin, user, estado_final=EstadoUsuarioEnum.ALTA)
    _evento(db_session, AccionUsuarioEnum.LOGIN, user, user,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.ALTA)
    db_session.commit()

    resp = client.get(_ENDPOINT, headers=headers_admin)
    assert resp.status_code == 200
    # Hay al menos los 2 eventos creados (puede haber más por el login del fixture admin)
    assert len(resp.json()) >= 2


def test_ca2_orden_cronologico_descendente(client, headers_admin, db_session):
    """Los resultados están ordenados de más reciente a más antiguo (fecha_hora desc)."""
    admin = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin3@test.com")
    user  = _nuevo_usuario(db_session, "OPERADOR", "op3@test.com")
    _evento(db_session, AccionUsuarioEnum.ALTA,  admin, user)
    _evento(db_session, AccionUsuarioEnum.LOGIN, user, user,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.ALTA)
    db_session.commit()

    resp = client.get(_ENDPOINT, headers=headers_admin)
    assert resp.status_code == 200
    fechas = [e["fecha_hora"] for e in resp.json() if e.get("fecha_hora")]
    # Verificar que los timestamps están en orden no-creciente (desc o iguales)
    for i in range(len(fechas) - 1):
        assert fechas[i] >= fechas[i + 1], (
            f"Orden incorrecto en posición {i}: {fechas[i]} < {fechas[i + 1]}"
        )


# ── CA-3: Filtrado por UUID de usuario afectado ───────────────────────────────

def test_ca3_filtro_usuario_afectado(client, headers_admin, db_session):
    """Solo devuelve eventos donde usuario_afectado_uuid coincide con el filtro."""
    admin  = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin4@test.com")
    user_a = _nuevo_usuario(db_session, "OPERADOR", "op4a@test.com")
    user_b = _nuevo_usuario(db_session, "OPERADOR", "op4b@test.com")
    _evento(db_session, AccionUsuarioEnum.ALTA, admin, user_a)
    _evento(db_session, AccionUsuarioEnum.ALTA, admin, user_b)
    db_session.commit()

    resp = client.get(_ENDPOINT, params={"usuario_afectado_uuid": str(user_a.uuid)},
                      headers=headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for ev in data:
        assert ev["usuario_afectado_uuid"] == str(user_a.uuid)


def test_ca3_filtro_afectado_excluye_otros_usuarios(client, headers_admin, db_session):
    """El filtro por afectado no incluye eventos de otros usuarios."""
    admin  = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin5@test.com")
    user_a = _nuevo_usuario(db_session, "OPERADOR", "op5a@test.com")
    user_b = _nuevo_usuario(db_session, "OPERADOR", "op5b@test.com")
    _evento(db_session, AccionUsuarioEnum.ALTA, admin, user_a)
    _evento(db_session, AccionUsuarioEnum.ALTA, admin, user_b)
    db_session.commit()

    resp = client.get(_ENDPOINT, params={"usuario_afectado_uuid": str(user_a.uuid)},
                      headers=headers_admin)
    assert resp.status_code == 200
    for ev in resp.json():
        assert ev["usuario_afectado_uuid"] != str(user_b.uuid)


# ── CA-4: Filtrado por UUID de usuario ejecutor ───────────────────────────────

def test_ca4_filtro_usuario_ejecutor(client, headers_admin, db_session):
    """Solo devuelve eventos donde usuario_ejecutor_uuid coincide con el filtro."""
    admin  = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin6@test.com")
    user_a = _nuevo_usuario(db_session, "OPERADOR", "op6a@test.com")
    user_b = _nuevo_usuario(db_session, "OPERADOR", "op6b@test.com")
    _evento(db_session, AccionUsuarioEnum.ALTA, admin, user_a)
    _evento(db_session, AccionUsuarioEnum.LOGIN, user_b, user_b,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.ALTA)
    db_session.commit()

    resp = client.get(_ENDPOINT, params={"usuario_ejecutor_uuid": str(admin.uuid)},
                      headers=headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    for ev in data:
        assert ev["usuario_ejecutor_uuid"] == str(admin.uuid)


# ── CA-5: UUID sin resultados devuelve lista vacía ────────────────────────────

def test_ca5_uuid_inexistente_devuelve_lista_vacia(client, headers_admin):
    """Un UUID sin registros asociados devuelve lista vacía (no error)."""
    uuid_inexistente = str(_uuid.uuid4())
    resp = client.get(_ENDPOINT, params={"usuario_afectado_uuid": uuid_inexistente},
                      headers=headers_admin)
    assert resp.status_code == 200
    assert resp.json() == []


def test_ca5_uuid_ejecutor_inexistente_devuelve_lista_vacia(client, headers_admin):
    """Un UUID de ejecutor sin registros devuelve lista vacía."""
    uuid_inexistente = str(_uuid.uuid4())
    resp = client.get(_ENDPOINT, params={"usuario_ejecutor_uuid": uuid_inexistente},
                      headers=headers_admin)
    assert resp.status_code == 200
    assert resp.json() == []


# ── CA-6: Datos mínimos requeridos en cada entrada ────────────────────────────

def test_ca6_cada_entrada_incluye_campos_requeridos(client, headers_admin, db_session):
    """Cada entrada del historial expone acción, ejecutor, afectado, estados y fecha."""
    admin = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin7@test.com")
    user  = _nuevo_usuario(db_session, "OPERADOR", "op7@test.com")
    _evento(db_session, AccionUsuarioEnum.ALTA, admin, user, estado_final=EstadoUsuarioEnum.ALTA)
    db_session.commit()

    resp = client.get(_ENDPOINT, headers=headers_admin)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    for entry in resp.json():
        assert "accion" in entry,                  "Falta campo 'accion'"
        assert "usuario_ejecutor_uuid" in entry,   "Falta campo 'usuario_ejecutor_uuid'"
        assert "usuario_afectado_uuid" in entry,   "Falta campo 'usuario_afectado_uuid'"
        assert "estado_final" in entry,            "Falta campo 'estado_final'"
        assert "fecha_hora" in entry,              "Falta campo 'fecha_hora'"


# ── CA-7: Historial incluye todos los tipos de acciones ───────────────────────

def test_ca7_historial_incluye_alta_login_logout(client, headers_admin, db_session):
    """Los tipos ALTA, LOGIN y LOGOUT quedan registrados y son recuperables."""
    admin = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin8@test.com")
    user  = _nuevo_usuario(db_session, "OPERADOR", "op8@test.com")
    _evento(db_session, AccionUsuarioEnum.ALTA,   admin, user,
            estado_final=EstadoUsuarioEnum.ALTA)
    _evento(db_session, AccionUsuarioEnum.LOGIN,  user,  user,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.ALTA)
    _evento(db_session, AccionUsuarioEnum.LOGOUT, user,  user,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.ALTA)
    db_session.commit()

    resp = client.get(_ENDPOINT, params={"usuario_afectado_uuid": str(user.uuid)},
                      headers=headers_admin)
    assert resp.status_code == 200
    acciones = {e["accion"] for e in resp.json()}
    assert "ALTA"   in acciones
    assert "LOGIN"  in acciones
    assert "LOGOUT" in acciones


def test_ca7_historial_incluye_baja(client, headers_admin, db_session):
    """El tipo BAJA también queda registrado en el historial."""
    admin = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin9@test.com")
    user  = _nuevo_usuario(db_session, "OPERADOR", "op9@test.com")
    _evento(db_session, AccionUsuarioEnum.BAJA, admin, user,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.BAJA)
    db_session.commit()

    resp = client.get(_ENDPOINT, params={"usuario_afectado_uuid": str(user.uuid)},
                      headers=headers_admin)
    assert resp.status_code == 200
    acciones = {e["accion"] for e in resp.json()}
    assert "BAJA" in acciones


def test_ca7_acciones_registradas_como_entradas_independientes(client, headers_admin, db_session):
    """Cada acción sobre un usuario aparece como entrada independiente."""
    admin = _nuevo_usuario(db_session, "ADMINISTRADOR", "admin10@test.com")
    user  = _nuevo_usuario(db_session, "OPERADOR", "op10@test.com")
    _evento(db_session, AccionUsuarioEnum.ALTA,   admin, user,
            estado_final=EstadoUsuarioEnum.ALTA)
    _evento(db_session, AccionUsuarioEnum.LOGIN,  user,  user,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.ALTA)
    _evento(db_session, AccionUsuarioEnum.LOGOUT, user,  user,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.ALTA)
    _evento(db_session, AccionUsuarioEnum.BAJA,   admin, user,
            estado_inicial=EstadoUsuarioEnum.ALTA, estado_final=EstadoUsuarioEnum.BAJA)
    db_session.commit()

    resp = client.get(_ENDPOINT, params={"usuario_afectado_uuid": str(user.uuid)},
                      headers=headers_admin)
    assert resp.status_code == 200
    assert len(resp.json()) == 4


# ── CA-8: Registros de solo lectura ──────────────────────────────────────────

def test_ca8_no_existe_endpoint_para_modificar(client, headers_admin):
    """No existe endpoint PUT/PATCH para modificar un evento de auditoría."""
    fake_uuid = str(_uuid.uuid4())
    resp = client.put(f"{_ENDPOINT}/{fake_uuid}", json={}, headers=headers_admin)
    assert resp.status_code in (404, 405)


def test_ca8_no_existe_endpoint_para_eliminar(client, headers_admin):
    """No existe endpoint DELETE para eliminar un evento de auditoría."""
    fake_uuid = str(_uuid.uuid4())
    resp = client.delete(f"{_ENDPOINT}/{fake_uuid}", headers=headers_admin)
    assert resp.status_code in (404, 405)


def test_ca8_endpoint_solo_permite_get(client, headers_admin):
    """El endpoint /auditoria/eventos solo acepta GET, no POST."""
    resp = client.post(_ENDPOINT, json={}, headers=headers_admin)
    assert resp.status_code in (404, 405)
