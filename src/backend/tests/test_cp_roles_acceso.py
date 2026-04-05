"""
Tests de control de acceso basado en roles.

Cubre los casos de prueba de la matriz de testing relacionados con
la adaptación de la interfaz y el acceso a funcionalidades según rol.

User Stories cubiertas:
  LP-102 — Adaptar interfaz según el rol del usuario autenticado
  LP-108 — Consultar historial de acciones por usuario
  LP-20  — Definir y persistir roles del sistema
  LP-97  — Registrar usuario con rol asignado

Casos de Prueba:
  CP-0092  LP-102 CA-4  Ocultamiento no equivale a protección suficiente (Unhappy Path)
  CP-0093  LP-102 CA-4  Ocultamiento no equivale a protección suficiente (Edge Case / sin token)
  CP-0119  LP-108 CA-1  Acceso exclusivo del Administrador (Happy Path)
  CP-0120  LP-108 CA-1  Acceso exclusivo del Administrador (Unhappy Path / rol incorrecto)
  CP-0121  LP-108 CA-1  Acceso exclusivo del Administrador (Edge Case / sin token)
  CP-0041  LP-20  CA-5  No se pueden crear usuarios sin un rol asignado (Unhappy Path)
  CP-0042  LP-20  CA-5  No se pueden crear usuarios sin un rol asignado (Edge Case / sin token)
  CP-0076  LP-97  CA-2  Registro exitoso de un usuario (Unhappy Path / rol incorrecto)
  CP-0077  LP-97  CA-2  Registro exitoso de un usuario (Edge Case / sin token)

Nota sobre CP-0041 y CP-0076:
  La matriz indica "401 Unauthorized" como resultado esperado para tokens de rol
  Supervisor/Operador en el endpoint de creación de usuarios. Sin embargo, dado que
  el endpoint requiere rol ADMINISTRADOR, un token válido con rol incorrecto recibe
  "403 Forbidden" (autenticado pero sin permisos). Los tests verifican el comportamiento
  real del sistema (403) para garantizar que pasen en el pipeline de CI.
"""


# ── Fixtures necesarios (provistos por conftest.py) ───────────────────────────
# client, headers_operador, headers_supervisor, headers_admin


_PAYLOAD_USUARIO = {
    "email": "nuevo@logitrack.com",
    "password": "Segura1234!",
    "rol_nombre": "OPERADOR",
}


# ── CP-0092: Operador intenta acceder a funcionalidad exclusiva vía API ────────

def test_cp0092_operador_no_puede_acceder_a_endpoint_de_admin(client, headers_operador):
    """
    CP-0092 — LP-102 CA-4 — Unhappy Path.
    Dato: JWT rol=Operador, firma HS256 correcta, exp > now.
    Precondición: las opciones de Supervisor/Admin no son visibles para Operador en la UI.
    Acción: el Operador intenta acceder directamente por API.
    Resultado esperado: el backend deniega el acceso con 403 Forbidden.
    """
    resp = client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador)
    assert resp.status_code == 403


def test_cp0092_operador_no_puede_ver_auditoria_de_usuarios(client, headers_operador):
    """
    CP-0092 — LP-102 CA-4 — Unhappy Path (complementario).
    El Operador intenta acceder a /auditoria/eventos (exclusivo de Administrador).
    Resultado esperado: 403 Forbidden.
    """
    resp = client.get("/auditoria/eventos", headers=headers_operador)
    assert resp.status_code == 403


# ── CP-0093: Sin token, intento de acceso a funcionalidades protegidas ─────────

def test_cp0093_sin_token_endpoint_admin_retorna_401(client):
    """
    CP-0093 — LP-102 CA-4 — Edge Case.
    Dato: Request HTTP sin header Authorization.
    Precondición: usuario no autenticado.
    Acción: intenta acceder a endpoint de administración por API.
    Resultado esperado: 401 Unauthorized.
    """
    resp = client.post("/usuarios", json=_PAYLOAD_USUARIO)
    assert resp.status_code == 401


def test_cp0093_sin_token_auditoria_retorna_401(client):
    """
    CP-0093 — LP-102 CA-4 — Edge Case (complementario).
    Sin token → GET /auditoria/eventos → 401 Unauthorized.
    """
    resp = client.get("/auditoria/eventos")
    assert resp.status_code == 401


# ── CP-0119: Administrador accede al historial de acciones ────────────────────

def test_cp0119_admin_puede_acceder_a_historial_de_acciones(client, headers_admin):
    """
    CP-0119 — LP-108 CA-1 — Happy Path.
    Dato: JWT rol=Administrador, firma HS256 correcta, exp > now.
    Precondición: usuario autenticado con rol Administrador.
    Acción: realiza la solicitud GET /auditoria/eventos.
    Resultado esperado: el sistema permite el acceso (200 OK).
    """
    resp = client.get("/auditoria/eventos", headers=headers_admin)
    assert resp.status_code == 200


def test_cp0119_admin_accede_historial_con_filtro_usuario_afectado(client, headers_admin):
    """
    CP-0119 — LP-108 CA-1 — Happy Path (con filtro).
    Administrador accede con filtro de usuario → 200 OK.
    """
    resp = client.get(
        "/auditoria/eventos?usuario_afectado_uuid=00000000-0000-0000-0000-000000000000",
        headers=headers_admin,
    )
    assert resp.status_code == 200


# ── CP-0120: Operador o Supervisor intenta acceder al historial ────────────────

def test_cp0120_operador_no_puede_ver_historial_retorna_403(client, headers_operador):
    """
    CP-0120 — LP-108 CA-1 — Unhappy Path.
    Dato: JWT rol=Operador, firma HS256 correcta, exp > now.
    Precondición: usuario autenticado con rol Operador.
    Acción: realiza solicitud al historial de acciones de usuario.
    Resultado esperado: 403 Forbidden.
    """
    resp = client.get("/auditoria/eventos", headers=headers_operador)
    assert resp.status_code == 403


def test_cp0120_supervisor_no_puede_ver_historial_retorna_403(client, headers_supervisor):
    """
    CP-0120 — LP-108 CA-1 — Unhappy Path (Supervisor).
    Dato: JWT rol=Supervisor, firma HS256 correcta, exp > now.
    Resultado esperado: 403 Forbidden.
    """
    resp = client.get("/auditoria/eventos", headers=headers_supervisor)
    assert resp.status_code == 403


# ── CP-0121: Sin token, intento de acceso al historial ────────────────────────

def test_cp0121_sin_token_historial_retorna_401(client):
    """
    CP-0121 — LP-108 CA-1 — Edge Case.
    Dato: Request HTTP sin header Authorization.
    Precondición: usuario no autenticado.
    Acción: realiza solicitud GET /auditoria/eventos.
    Resultado esperado: 401 Unauthorized.
    """
    resp = client.get("/auditoria/eventos")
    assert resp.status_code == 401


# ── CP-0041: Supervisor intenta crear usuario sin rol ─────────────────────────

def test_cp0041_supervisor_no_puede_crear_usuario_sin_rol(client, headers_supervisor):
    """
    CP-0041 — LP-20 CA-5 — Unhappy Path.
    Dato: JWT rol=Supervisor, firma HS256 correcta, exp > now.
    Precondición: el supervisor intenta crear un usuario sin asignarle un rol.
    Acción: el sistema intenta persistir el registro.
    Resultado esperado: acceso denegado (403 Forbidden).
    Nota: la matriz indica 401, pero el backend retorna 403 porque el token es
    válido pero el rol Supervisor no tiene permiso para crear usuarios.
    """
    payload = {"email": "sinrol@logitrack.com", "password": "Segura1234!"}
    resp = client.post("/usuarios", json=payload, headers=headers_supervisor)
    assert resp.status_code == 403


def test_cp0041_supervisor_no_puede_crear_usuario_con_rol_valido(client, headers_supervisor):
    """
    CP-0041 — LP-20 CA-5 — Unhappy Path (complementario).
    Supervisor con payload completo intenta crear usuario → 403 Forbidden.
    La denegación ocurre por rol, antes de validar el payload.
    """
    resp = client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_supervisor)
    assert resp.status_code == 403


# ── CP-0042: Sin token, intento de acceso al formulario de registro ───────────

def test_cp0042_sin_token_registro_usuario_retorna_401(client):
    """
    CP-0042 — LP-20 CA-5 — Edge Case.
    Dato: Request HTTP sin header Authorization.
    Precondición: usuario no autenticado.
    Acción: intenta acceder al formulario de registro.
    Resultado esperado: 401 Unauthorized.
    """
    resp = client.post("/usuarios", json=_PAYLOAD_USUARIO)
    assert resp.status_code == 401


# ── CP-0076: Operador intenta registrar usuario ───────────────────────────────

def test_cp0076_operador_no_puede_registrar_usuario(client, headers_operador):
    """
    CP-0076 — LP-97 CA-2 — Unhappy Path.
    Dato: JWT rol=Operador, firma HS256 correcta, exp > now.
    Precondición: operador completa el formulario de registro.
    Acción: confirma el registro.
    Resultado esperado: acceso denegado (403 Forbidden).
    Nota: la matriz indica 401, pero el backend retorna 403 porque el token es
    válido pero el rol Operador no tiene permiso para registrar usuarios.
    """
    resp = client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador)
    assert resp.status_code == 403


def test_cp0076_operador_no_puede_registrar_usuario_independientemente_del_email(
    client, headers_operador
):
    """
    CP-0076 — LP-97 CA-2 — Unhappy Path (variante).
    El 403 no depende del email: cualquier intento del Operador es bloqueado.
    """
    for email in ["a@test.com", "admin@empresa.com", "otro@logitrack.com"]:
        payload = {**_PAYLOAD_USUARIO, "email": email}
        assert client.post("/usuarios", json=payload, headers=headers_operador).status_code == 403


# ── CP-0077: Sin token, intento de registro de usuario ───────────────────────

def test_cp0077_sin_token_registro_retorna_401(client):
    """
    CP-0077 — LP-97 CA-2 — Edge Case.
    Dato: Request HTTP sin header Authorization.
    Precondición: usuario no autenticado.
    Acción: confirma el registro.
    Resultado esperado: 401 Unauthorized.
    """
    resp = client.post("/usuarios", json=_PAYLOAD_USUARIO)
    assert resp.status_code == 401
