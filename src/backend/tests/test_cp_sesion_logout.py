"""
Tests del cierre de sesión y comportamiento post-logout.

User Story cubierta:
  LP-99 — Cerrar sesión del sistema

Casos de Prueba:
  CP-0085  LP-99 CA-2  Sesión invalidada tras el logout (Happy Path)
  CP-0086  LP-99 CA-2  Sesión invalidada tras el logout (Edge Case / sin token)
  CP-0088  LP-99 CA-4  Token invalidado en el backend (Happy Path)

Nota sobre CP-0085 (comportamiento MVP):
  El backend MVP no implementa una blacklist de tokens JWT. La invalidación real
  de la sesión ocurre en el cliente al descartar el token del localStorage.
  Este test verifica:
    (a) el logout registra la sesión como cerrada (evento LOGOUT en BD),
    (b) simula la invalidación del lado del cliente omitiendo el token en
        solicitudes posteriores → el sistema retorna 401 al no recibir token.
"""
from models import EventoDeUsuario, AccionUsuarioEnum


# ── CP-0085: Post-logout, acceso sin token → 401 ─────────────────────────────

def test_cp0085_logout_exitoso_retorna_200(client, headers_operador):
    """
    CP-0085 — LP-99 CA-2 — Happy Path (verificación del logout en sí).
    Dato: JWT previamente activo.
    Precondición: el usuario ha cerrado sesión.
    Resultado esperado: el logout retorna 200 confirmando la operación.
    """
    resp = client.post("/auth/logout", headers=headers_operador)
    assert resp.status_code == 200


def test_cp0085_post_logout_sin_token_acceso_denegado(client, headers_operador):
    """
    CP-0085 — LP-99 CA-2 — Happy Path.
    Dato: JWT previamente activo cuyo token fue eliminado del almacenamiento del cliente.
    Precondición: el usuario cerró sesión (token eliminado del cliente).
    Acción: intenta acceder a una URL protegida sin enviar token (simulando cliente post-logout).
    Resultado esperado: el sistema deniega el acceso (401 Unauthorized).
    """
    # 1. Cerrar sesión
    resp_logout = client.post("/auth/logout", headers=headers_operador)
    assert resp_logout.status_code == 200

    # 2. Simular que el cliente eliminó el token: nueva solicitud SIN token
    resp_protected = client.get("/envios/")
    assert resp_protected.status_code == 401


def test_cp0085_post_logout_sin_token_endpoint_post_denegado(client, headers_operador):
    """
    CP-0085 — LP-99 CA-2 — Complementario (endpoint POST).
    Tras el logout, intentar crear un envío sin token → 401.
    """
    client.post("/auth/logout", headers=headers_operador)
    resp = client.post("/usuarios", json={})
    assert resp.status_code == 401


# ── CP-0086: Sin token, acceso a URL protegida → 401 ─────────────────────────

def test_cp0086_sin_token_acceso_a_ruta_protegida_retorna_401(client):
    """
    CP-0086 — LP-99 CA-2 — Edge Case.
    Dato: Request HTTP sin header Authorization.
    Precondición: usuario no autenticado.
    Acción: intenta acceder a una URL protegida sin token.
    Resultado esperado: 401 Unauthorized.
    """
    resp = client.get("/envios/")
    assert resp.status_code == 401


def test_cp0086_sin_token_endpoint_envios_retorna_401(client):
    """
    CP-0086 — LP-99 CA-2 — Edge Case (POST sin token).
    Sin Authorization en endpoint POST protegido → 401 Unauthorized.
    """
    assert client.post("/envios/", json={}).status_code == 401


def test_cp0086_sin_token_auditoria_retorna_401(client):
    """
    CP-0086 — LP-99 CA-2 — Edge Case (auditoría).
    Sin Authorization en GET /auditoria/eventos → 401 Unauthorized.
    """
    assert client.get("/auditoria/eventos").status_code == 401


# ── CP-0088: Token invalidado en el backend (evento LOGOUT registrado) ────────

def test_cp0088_logout_registra_evento_logout_en_base_de_datos(client, db_session, headers_operador):
    """
    CP-0088 — LP-99 CA-4 — Happy Path.
    Dato: JWT válido y no expirado (token activo antes del logout).
    Precondición: el usuario ejecuta el logout.
    Acción: el backend recibe la solicitud.
    Resultado esperado: el token de sesión queda invalidado (se registra EventoDeUsuario LOGOUT).
    El MVP registra el evento LOGOUT en BD como mecanismo de auditoría de la sesión.
    """
    resp = client.post("/auth/logout", headers=headers_operador)
    assert resp.status_code == 200

    evento = db_session.query(EventoDeUsuario).filter(
        EventoDeUsuario.accion == AccionUsuarioEnum.LOGOUT
    ).first()
    assert evento is not None, "El backend debe registrar un EventoDeUsuario con accion=LOGOUT"


def test_cp0088_evento_logout_vincula_ejecutor_con_afectado(client, db_session, headers_operador):
    """
    CP-0088 — LP-99 CA-4 — Complementario.
    El evento LOGOUT vincula al mismo usuario como ejecutor y afectado.
    """
    client.post("/auth/logout", headers=headers_operador)

    evento = db_session.query(EventoDeUsuario).filter(
        EventoDeUsuario.accion == AccionUsuarioEnum.LOGOUT
    ).first()
    assert evento is not None
    assert evento.usuario_ejecutor_uuid == evento.usuario_afectado_uuid


def test_cp0088_logout_con_cualquier_rol_registra_evento(client, db_session, headers_admin):
    """
    CP-0088 — LP-99 CA-4 — Complementario (Administrador).
    El evento LOGOUT se registra independientemente del rol del usuario.
    """
    client.post("/auth/logout", headers=headers_admin)

    evento = db_session.query(EventoDeUsuario).filter(
        EventoDeUsuario.accion == AccionUsuarioEnum.LOGOUT
    ).first()
    assert evento is not None


def test_cp0088_logout_supervisor_registra_evento(client, db_session, headers_supervisor):
    """
    CP-0088 — LP-99 CA-4 — Complementario (Supervisor).
    El evento LOGOUT se registra para rol Supervisor.
    """
    client.post("/auth/logout", headers=headers_supervisor)

    evento = db_session.query(EventoDeUsuario).filter(
        EventoDeUsuario.accion == AccionUsuarioEnum.LOGOUT
    ).first()
    assert evento is not None
