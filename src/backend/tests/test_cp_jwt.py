"""
Tests de emisión y validación de tokens JWT, y protección de rutas autenticadas.

User Stories cubiertas:
  LP-21  — Autenticación de usuarios (CA-7: Protección de rutas autenticadas)
  LP-254 — Emitir y validar tokens JWT en cada interacción autenticada

Casos de Prueba:
  CP-0053  LP-21  CA-7  Protección de rutas autenticadas (Happy Path / token inválido-expirado)
  CP-0054  LP-21  CA-7  Protección de rutas autenticadas (Edge Case / sin token)
  CP-0301  LP-254 CA-1  Token generado al hacer login exitoso (Happy Path)
  CP-0302  LP-254 CA-1  Token generado al hacer login exitoso (Unhappy Path / contraseña incorrecta)
  CP-0303  LP-254 CA-2  Token con tiempo de expiración de 8 horas (Happy Path)
  CP-0304  LP-254 CA-3  Token enviado en header Authorization (Happy Path)
  CP-0305  LP-254 CA-3  Token enviado en header Authorization (Unhappy Path / formato incorrecto)
  CP-0307  LP-254 CA-5  Token expirado devuelve 401 (Unhappy Path)
  CP-0308  LP-254 CA-6  Token con firma inválida devuelve 401 (Unhappy Path / payload modificado)
  CP-0309  LP-254 CA-6  Token con firma inválida devuelve 401 (Unhappy Path / SECRET_KEY distinta)
  CP-0310  LP-254 CA-7  Rol insuficiente devuelve 403 (Unhappy Path)
  CP-0311  LP-254 CA-8  Request sin token devuelve 401 (Unhappy Path)
  CP-0312  LP-254 CA-8  Request sin token devuelve 401 (Unhappy Path / Bearer vacío)
"""
import os
from datetime import datetime, timedelta, timezone

from jose import jwt

_SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
_ALGORITHM  = "HS256"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _token_expirado(rol: str = "OPERADOR") -> str:
    """JWT ya expirado (exp en el pasado), firmado con la clave correcta."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub":   "00000000-0000-0000-0000-000000000001",
        "email": "expirado@logitrack.com",
        "rol":   rol,
        "iat":   int((now - timedelta(hours=9)).timestamp()),
        "exp":   int((now - timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def _token_firma_invalida(rol: str = "OPERADOR") -> str:
    """JWT estructuralmente válido pero firmado con clave incorrecta."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub":   "00000000-0000-0000-0000-000000000002",
        "email": "malo@logitrack.com",
        "rol":   rol,
        "iat":   int(now.timestamp()),
        "exp":   int((now + timedelta(hours=8)).timestamp()),
    }
    return jwt.encode(payload, "clave-secreta-completamente-distinta", algorithm=_ALGORITHM)


# ── CP-0053: Token inválido o expirado → 401 en ruta protegida ───────────────

def test_cp0053_token_expirado_en_ruta_protegida_retorna_401(client, headers_operador):
    """
    CP-0053 — LP-21 CA-7 — Happy Path (escenario de falla de autenticación).
    Dato: JWT con firma manipulada o exp < now (token inválido o expirado).
    Precondición: usuario no autenticado con sesión válida.
    Acción: el sistema detecta la ausencia de sesión válida.
    Resultado esperado: 401 Unauthorized (redirige al login sin mostrar contenido protegido).
    """
    headers = {"Authorization": f"Bearer {_token_expirado()}"}
    resp = client.get("/envios/", headers=headers)
    assert resp.status_code == 401


def test_cp0053_token_con_firma_invalida_en_ruta_protegida_retorna_401(client):
    """
    CP-0053 — LP-21 CA-7 — Happy Path (token con firma manipulada).
    Token con firma incorrecta en ruta protegida → 401 Unauthorized.
    """
    headers = {"Authorization": f"Bearer {_token_firma_invalida()}"}
    resp = client.get("/envios/", headers=headers)
    assert resp.status_code == 401


def test_cp0053_token_malformado_en_ruta_protegida_retorna_401(client):
    """
    CP-0053 — LP-21 CA-7 — Variante: string que no es JWT válido → 401.
    """
    headers = {"Authorization": "Bearer esto.no.es.un.jwt.valido"}
    resp = client.get("/envios/", headers=headers)
    assert resp.status_code == 401


# ── CP-0054: Sin token → 401 en ruta protegida ───────────────────────────────

def test_cp0054_sin_token_ruta_protegida_retorna_401(client):
    """
    CP-0054 — LP-21 CA-7 — Edge Case.
    Dato: Request HTTP sin header Authorization.
    Precondición: usuario no autenticado.
    Acción: el sistema detecta la ausencia de sesión válida.
    Resultado esperado: 401 Unauthorized.
    """
    resp = client.get("/envios/")
    assert resp.status_code == 401


def test_cp0054_sin_token_en_endpoint_post_retorna_401(client):
    """
    CP-0054 — LP-21 CA-7 — Edge Case (POST protegido).
    Sin Authorization en endpoint POST protegido → 401 Unauthorized.
    """
    resp = client.post("/usuarios", json={})
    assert resp.status_code == 401


# ── CP-0301: Login exitoso genera JWT con campos requeridos ──────────────────

def test_cp0301_login_exitoso_retorna_200_con_access_token(client, headers_operador):
    """
    CP-0301 — LP-254 CA-1 — Happy Path.
    Dato: email y contraseña válidos, usuario existente en BD.
    Precondición: el usuario envía credenciales válidas al endpoint de login.
    Acción: el backend valida las credenciales exitosamente.
    Resultado esperado: se retorna un JWT firmado (HS256) con uuid, email, rol, iat, exp.
    """
    resp = client.post("/auth/login", json={
        "email": "operador@test.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_cp0301_payload_jwt_contiene_sub(client, headers_operador):
    """CP-0301 — LP-254 CA-1 — El payload del JWT incluye 'sub' (UUID del usuario)."""
    resp = client.post("/auth/login", json={"email": "operador@test.com", "password": "password123"})
    payload = jwt.decode(resp.json()["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
    assert "sub" in payload and payload["sub"] != ""


def test_cp0301_payload_jwt_contiene_email(client, headers_operador):
    """CP-0301 — LP-254 CA-1 — El payload del JWT incluye 'email'."""
    resp = client.post("/auth/login", json={"email": "operador@test.com", "password": "password123"})
    payload = jwt.decode(resp.json()["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
    assert payload.get("email") == "operador@test.com"


def test_cp0301_payload_jwt_contiene_rol(client, headers_operador):
    """CP-0301 — LP-254 CA-1 — El payload del JWT incluye 'rol'."""
    resp = client.post("/auth/login", json={"email": "operador@test.com", "password": "password123"})
    payload = jwt.decode(resp.json()["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
    assert payload.get("rol") == "OPERADOR"


def test_cp0301_payload_jwt_contiene_iat_y_exp(client, headers_operador):
    """CP-0301 — LP-254 CA-1 — El payload del JWT incluye 'iat' y 'exp'."""
    resp = client.post("/auth/login", json={"email": "operador@test.com", "password": "password123"})
    payload = jwt.decode(resp.json()["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
    assert "iat" in payload and "exp" in payload


# ── CP-0302: Login con contraseña incorrecta no emite token ──────────────────

def test_cp0302_login_contrasena_incorrecta_retorna_401(client, headers_operador):
    """
    CP-0302 — LP-254 CA-1 — Unhappy Path.
    Dato: email válido + contraseña incorrecta.
    Precondición: el usuario envía credenciales inválidas.
    Acción: el backend rechaza las credenciales.
    Resultado esperado: no se emite ningún token JWT; se retorna error 401.
    """
    resp = client.post("/auth/login", json={
        "email": "operador@test.com",
        "password": "contrasena-incorrecta",
    })
    assert resp.status_code == 401
    assert "access_token" not in resp.json()


def test_cp0302_login_email_inexistente_retorna_401(client):
    """
    CP-0302 — LP-254 CA-1 — Unhappy Path (variante: email no registrado).
    Email inexistente → no se emite token; 401 Unauthorized.
    """
    resp = client.post("/auth/login", json={
        "email": "noexiste@logitrack.com",
        "password": "cualquierCosa123",
    })
    assert resp.status_code == 401
    assert "access_token" not in resp.json()


# ── CP-0303: Expiración del token exactamente 8 horas ────────────────────────

def test_cp0303_exp_es_igual_a_iat_mas_28800_segundos(client, headers_operador):
    """
    CP-0303 — LP-254 CA-2 — Happy Path.
    Dato: token JWT generado en login exitoso.
    Precondición: se acaba de generar un token JWT válido.
    Acción: se decodifica el payload del token.
    Resultado esperado: exp == iat + 28800 (8 horas en segundos).
    """
    resp = client.post("/auth/login", json={"email": "operador@test.com", "password": "password123"})
    payload = jwt.decode(resp.json()["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
    assert payload["exp"] - payload["iat"] == 8 * 3600


def test_cp0303_token_recien_emitido_no_esta_expirado(client, headers_operador):
    """
    CP-0303 — LP-254 CA-2 — Complementario.
    El token recién emitido tiene exp > now.
    """
    resp = client.post("/auth/login", json={"email": "operador@test.com", "password": "password123"})
    payload = jwt.decode(resp.json()["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
    ahora = int(datetime.now(timezone.utc).timestamp())
    assert payload["exp"] > ahora


# ── CP-0304: Token en header Authorization: Bearer ───────────────────────────

def test_cp0304_request_con_bearer_token_valido_es_aceptado(client, headers_operador):
    """
    CP-0304 — LP-254 CA-3 — Happy Path.
    Dato: token JWT válido, endpoint protegido cualquiera.
    Precondición: el frontend tiene un token JWT válido almacenado.
    Acción: realiza un request a un endpoint protegido.
    Resultado esperado: el header Authorization: Bearer <token> es aceptado (200 OK).
    """
    resp = client.get("/envios/", headers=headers_operador)
    assert resp.status_code == 200


def test_cp0304_header_authorization_contiene_prefijo_bearer(client, headers_operador):
    """
    CP-0304 — LP-254 CA-3 — Complementario.
    El fixture headers_operador incluye el prefijo 'Bearer ' en el header.
    """
    assert headers_operador.get("Authorization", "").startswith("Bearer ")


# ── CP-0305: Token con formato de header incorrecto → 401 ────────────────────

def test_cp0305_token_con_prefijo_incorrecto_retorna_401(client, headers_operador):
    """
    CP-0305 — LP-254 CA-3 — Unhappy Path.
    Dato: token JWT válido, header con formato incorrecto (Token <token>).
    Precondición: el frontend envía el token con un formato distinto al esperado.
    Acción: el backend procesa la solicitud.
    Resultado esperado: el backend rechaza el request y retorna 401 Unauthorized.
    """
    resp_login = client.post("/auth/login", json={"email": "operador@test.com", "password": "password123"})
    token = resp_login.json()["access_token"]
    headers = {"Authorization": f"Token {token}"}
    assert client.get("/envios/", headers=headers).status_code == 401


def test_cp0305_token_sin_prefijo_alguno_retorna_401(client, headers_operador):
    """
    CP-0305 — LP-254 CA-3 — Unhappy Path (sin prefijo).
    Token enviado directamente sin prefijo Bearer → 401 Unauthorized.
    """
    resp_login = client.post("/auth/login", json={"email": "operador@test.com", "password": "password123"})
    token = resp_login.json()["access_token"]
    headers = {"Authorization": token}
    assert client.get("/envios/", headers=headers).status_code == 401


# ── CP-0307: Token expirado devuelve 401 ─────────────────────────────────────

def test_cp0307_token_expirado_retorna_401_en_endpoint_protegido(client, headers_operador):
    """
    CP-0307 — LP-254 CA-5 — Unhappy Path.
    Dato: token JWT con exp en el pasado.
    Precondición: el frontend posee un token cuya fecha de expiración ya pasó.
    Acción: envía ese token en el header Authorization a un endpoint protegido.
    Resultado esperado: el backend retorna 401 Unauthorized; no ejecuta lógica de negocio.
    """
    headers = {"Authorization": f"Bearer {_token_expirado()}"}
    assert client.get("/envios/", headers=headers).status_code == 401


def test_cp0307_token_expirado_retorna_401_en_post(client, headers_operador):
    """
    CP-0307 — LP-254 CA-5 — Unhappy Path (POST).
    Token expirado en endpoint POST protegido → 401 Unauthorized.
    """
    headers = {"Authorization": f"Bearer {_token_expirado()}"}
    assert client.post("/usuarios", json={}, headers=headers).status_code == 401


# ── CP-0308: Token con payload modificado → 401 ──────────────────────────────

def test_cp0308_token_payload_modificado_retorna_401(client, headers_operador):
    """
    CP-0308 — LP-254 CA-6 — Unhappy Path.
    Dato: token JWT manipulado (payload modificado sin re-firmar).
    Precondición: se tiene un token con el payload alterado manualmente.
    Acción: se envía el token manipulado en el header Authorization.
    Resultado esperado: el backend detecta la firma inválida, retorna 401 Unauthorized.
    """
    # Creamos un token con sub vacío y firma incorrecta (payload alterado)
    now = datetime.now(timezone.utc)
    payload_alterado = {
        "sub":   "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "email": "atacante@hack.com",
        "rol":   "ADMINISTRADOR",
        "iat":   int(now.timestamp()),
        "exp":   int((now + timedelta(hours=8)).timestamp()),
    }
    token_manipulado = jwt.encode(payload_alterado, "clave-falsa-del-atacante", algorithm=_ALGORITHM)
    headers = {"Authorization": f"Bearer {token_manipulado}"}
    assert client.get("/envios/", headers=headers).status_code == 401


def test_cp0308_token_estructura_invalida_retorna_401(client):
    """
    CP-0308 — LP-254 CA-6 — Variante.
    String que simula un token manipulado (estructura inválida) → 401.
    """
    headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJyb2wiOiJBRE1JTiJ9.firma_falsa"}
    assert client.get("/envios/", headers=headers).status_code == 401


# ── CP-0309: Token firmado con SECRET_KEY distinta → 401 ─────────────────────

def test_cp0309_token_firmado_con_secret_key_distinta_retorna_401(client, headers_operador):
    """
    CP-0309 — LP-254 CA-6 — Unhappy Path.
    Dato: token JWT generado con una SECRET_KEY distinta a la del entorno.
    Precondición: el atacante genera un token válido estructuralmente pero firmado con otra clave.
    Acción: envía ese token al backend.
    Resultado esperado: el backend rechaza el token con 401 Unauthorized; no ejecuta operación.
    """
    headers = {"Authorization": f"Bearer {_token_firma_invalida()}"}
    assert client.get("/envios/", headers=headers).status_code == 401


def test_cp0309_token_con_clave_erronea_rechazado_en_delete(client, headers_operador):
    """
    CP-0309 — LP-254 CA-6 — Complementario.
    Token con SECRET_KEY incorrecta en endpoint DELETE → 401 Unauthorized.
    """
    headers = {"Authorization": f"Bearer {_token_firma_invalida()}"}
    assert client.delete("/envios/LT-00000001", headers=headers).status_code == 401


# ── CP-0310: Rol insuficiente devuelve 403 ────────────────────────────────────

def test_cp0310_operador_en_endpoint_exclusivo_de_admin_retorna_403(client, headers_operador):
    """
    CP-0310 — LP-254 CA-7 — Unhappy Path.
    Dato: token JWT válido y no expirado, con rol Operador accediendo a endpoint de Administrador.
    Precondición: el usuario tiene un token válido con un rol sin permisos para el endpoint.
    Acción: realiza un request a ese endpoint protegido.
    Resultado esperado: el backend retorna 403 Forbidden; no ejecuta la lógica de negocio.
    """
    resp = client.post("/usuarios", json={
        "email": "x@x.com",
        "password": "Segura1234!",
        "rol_nombre": "OPERADOR",
    }, headers=headers_operador)
    assert resp.status_code == 403


def test_cp0310_admin_en_endpoint_exclusivo_de_operador_retorna_403(client, headers_admin):
    """
    CP-0310 — LP-254 CA-7 — Complementario (Admin sin permisos en endpoint de envíos).
    Admin intenta acceder a GET /envios/ (requiere Operador/Supervisor) → 403 Forbidden.
    """
    assert client.get("/envios/", headers=headers_admin).status_code == 403


# ── CP-0311: Sin token devuelve 401 ──────────────────────────────────────────

def test_cp0311_sin_token_en_endpoint_protegido_retorna_401(client):
    """
    CP-0311 — LP-254 CA-8 — Unhappy Path.
    Dato: Request HTTP sin header Authorization.
    Precondición: se realiza un request a un endpoint protegido sin ningún header de autenticación.
    Acción: el backend procesa la solicitud.
    Resultado esperado: el backend retorna 401 Unauthorized; no ejecuta ninguna lógica de negocio.
    """
    assert client.get("/envios/").status_code == 401


def test_cp0311_sin_token_en_post_envios_retorna_401(client):
    """CP-0311 — LP-254 CA-8 — Sin token en POST /envios/ → 401."""
    assert client.post("/envios/", json={}).status_code == 401


def test_cp0311_sin_token_en_delete_retorna_401(client):
    """CP-0311 — LP-254 CA-8 — Sin token en DELETE /envios/{id} → 401."""
    assert client.delete("/envios/LT-00000001").status_code == 401


def test_cp0311_sin_token_en_auditoria_retorna_401(client):
    """CP-0311 — LP-254 CA-8 — Sin token en GET /auditoria/eventos → 401."""
    assert client.get("/auditoria/eventos").status_code == 401


# ── CP-0312: Bearer con token vacío devuelve 401 ─────────────────────────────

def test_cp0312_bearer_token_vacio_retorna_401(client):
    """
    CP-0312 — LP-254 CA-8 — Unhappy Path.
    Dato: Request con header Authorization: Bearer  (token vacío).
    Precondición: se envía el header de autorización pero sin token.
    Acción: el backend procesa la solicitud.
    Resultado esperado: el backend retorna 401 Unauthorized.
    """
    headers = {"Authorization": "Bearer "}
    assert client.get("/envios/", headers=headers).status_code == 401


def test_cp0312_bearer_token_solo_espacios_retorna_401(client):
    """
    CP-0312 — LP-254 CA-8 — Variante: Bearer con solo espacios → 401.
    """
    headers = {"Authorization": "Bearer   "}
    resp = client.get("/envios/", headers=headers)
    assert resp.status_code == 401
