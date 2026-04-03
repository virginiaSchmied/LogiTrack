"""
Tests unitarios para autenticación de usuarios y manejo de tokens JWT.

Historia: Como usuario del sistema, quiero autenticarme con mis credenciales
para recibir un token JWT que me permita operar según mi rol.

Endpoints: POST /auth/login

Criterios de Aceptación cubiertos:
  CA-1 — Token generado al hacer login exitoso (sub, email, rol, iat, exp)
  CA-2 — Token con tiempo de expiración de 8 horas
  CA-3 — Token enviado en header Authorization (verificado en el lado backend)
  CA-4 — Backend valida el token en cada request protegido
  CA-5 — Token expirado devuelve 401
  CA-6 — Token con firma inválida devuelve 401
  CA-7 — Rol insuficiente devuelve 403
  CA-8 — Request sin token devuelve 401
  CA-9 — Clave secreta leída desde variable de entorno (NFR / inspección estática)
"""
import os
import pathlib
from datetime import datetime, timedelta, timezone

from jose import jwt

_SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
_ALGORITHM  = "HS256"


def _login(client, email: str, password: str) -> dict:
    """Hace login y devuelve el JSON de la respuesta."""
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login falló: {resp.text}"
    return resp.json()


def _token_expirado(sub: str = "00000000-0000-0000-0000-000000000000",
                    rol: str = "OPERADOR") -> str:
    """Genera un JWT ya expirado (exp en el pasado) firmado con la clave correcta."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub":   sub,
        "email": "expirado@logitrack.com",
        "rol":   rol,
        "iat":   int((now - timedelta(hours=9)).timestamp()),
        "exp":   int((now - timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def _token_firma_invalida(sub: str = "00000000-0000-0000-0000-000000000000",
                          rol: str = "OPERADOR") -> str:
    """Genera un JWT válido en forma pero firmado con una clave incorrecta."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub":   sub,
        "email": "malo@logitrack.com",
        "rol":   rol,
        "iat":   int(now.timestamp()),
        "exp":   int((now + timedelta(hours=8)).timestamp()),
    }
    return jwt.encode(payload, "clave-secreta-equivocada", algorithm=_ALGORITHM)


# ── CA-1: Token generado al hacer login exitoso ───────────────────────────────

class TestCA1TokenGeneradoAlLogin:

    def test_login_exitoso_retorna_200(self, client, headers_operador):
        """CA-1 — Login con credenciales válidas → 200 OK."""
        resp = client.post("/auth/login", json={
            "email": "operador@test.com",
            "password": "password123",
        })
        assert resp.status_code == 200

    def test_login_exitoso_incluye_access_token(self, client, headers_operador):
        """CA-1 — La respuesta de login incluye el campo access_token."""
        data = _login(client, "operador@test.com", "password123")
        assert "access_token" in data
        assert data["access_token"] != ""

    def test_token_payload_contiene_sub(self, client, headers_operador):
        """CA-1 — El payload del JWT incluye el campo 'sub' (UUID del usuario)."""
        data = _login(client, "operador@test.com", "password123")
        payload = jwt.decode(data["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
        assert "sub" in payload
        assert payload["sub"] != ""

    def test_token_payload_contiene_email(self, client, headers_operador):
        """CA-1 — El payload del JWT incluye el campo 'email'."""
        data = _login(client, "operador@test.com", "password123")
        payload = jwt.decode(data["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
        assert payload.get("email") == "operador@test.com"

    def test_token_payload_contiene_rol(self, client, headers_operador):
        """CA-1 — El payload del JWT incluye el campo 'rol'."""
        data = _login(client, "operador@test.com", "password123")
        payload = jwt.decode(data["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
        assert payload.get("rol") == "OPERADOR"

    def test_token_payload_contiene_iat(self, client, headers_operador):
        """CA-1 — El payload del JWT incluye el campo 'iat' (issued at)."""
        data = _login(client, "operador@test.com", "password123")
        payload = jwt.decode(data["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
        assert "iat" in payload

    def test_token_payload_contiene_exp(self, client, headers_operador):
        """CA-1 — El payload del JWT incluye el campo 'exp' (expiration)."""
        data = _login(client, "operador@test.com", "password123")
        payload = jwt.decode(data["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
        assert "exp" in payload

    def test_login_incorrecto_retorna_401(self, client, headers_operador):
        """CA-1 — Credenciales incorrectas → 401 Unauthorized."""
        resp = client.post("/auth/login", json={
            "email": "operador@test.com",
            "password": "contrasena-incorrecta",
        })
        assert resp.status_code == 401

    def test_login_email_inexistente_retorna_401(self, client):
        """CA-1 — Email no registrado → 401 Unauthorized."""
        resp = client.post("/auth/login", json={
            "email": "noexiste@logitrack.com",
            "password": "cualquierCosa123",
        })
        assert resp.status_code == 401


# ── CA-2: Token con expiración de 8 horas ────────────────────────────────────

class TestCA2ExpiracionOchoHoras:

    def test_diferencia_exp_iat_es_exactamente_8_horas(self, client, headers_operador):
        """CA-2 — exp − iat == 8 × 3600 segundos."""
        data = _login(client, "operador@test.com", "password123")
        payload = jwt.decode(data["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
        assert payload["exp"] - payload["iat"] == 8 * 3600

    def test_exp_es_mayor_que_iat(self, client, headers_operador):
        """CA-2 — exp siempre es posterior a iat."""
        data = _login(client, "operador@test.com", "password123")
        payload = jwt.decode(data["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
        assert payload["exp"] > payload["iat"]

    def test_token_no_esta_expirado_al_emitirse(self, client, headers_operador):
        """CA-2 — El token recién emitido no está expirado."""
        data = _login(client, "operador@test.com", "password123")
        payload = jwt.decode(data["access_token"], _SECRET_KEY, algorithms=[_ALGORITHM])
        ahora = int(datetime.now(timezone.utc).timestamp())
        assert payload["exp"] > ahora


# ── CA-3: Token enviado en header Authorization ───────────────────────────────

class TestCA3TokenEnHeader:

    def test_request_con_bearer_token_es_aceptado(self, client, headers_operador):
        """CA-3 — Request con Authorization: Bearer <token> válido → 200."""
        resp = client.get("/envios/", headers=headers_operador)
        assert resp.status_code == 200

    def test_token_sin_prefijo_bearer_retorna_401(self, client, headers_operador):
        """CA-3 — Token sin el prefijo 'Bearer ' → 401 (formato incorrecto)."""
        data = _login(client, "operador@test.com", "password123")
        headers = {"Authorization": data["access_token"]}
        assert client.get("/envios/", headers=headers).status_code == 401

    def test_header_authorization_ausente_retorna_401(self, client):
        """CA-3/CA-8 — Sin header Authorization → 401."""
        assert client.get("/envios/").status_code == 401


# ── CA-4: Backend valida token en cada request ───────────────────────────────

class TestCA4ValidacionPorRequest:

    def test_token_valido_permite_acceso_a_endpoint_protegido(self, client, headers_operador):
        """CA-4 — Token válido → el backend ejecuta la lógica y responde 200."""
        assert client.get("/envios/", headers=headers_operador).status_code == 200

    def test_token_invalido_bloquea_endpoint_protegido(self, client):
        """CA-4 — Token inválido → el backend rechaza antes de ejecutar lógica."""
        headers = {"Authorization": "Bearer esto.no.es.un.jwt"}
        assert client.get("/envios/", headers=headers).status_code == 401

    def test_token_valido_es_requerido_en_post(self, client):
        """CA-4 — Endpoint POST protegido también requiere token válido."""
        assert client.post("/usuarios", json={}).status_code == 401

    def test_token_valido_es_requerido_en_delete(self, client):
        """CA-4 — Endpoint DELETE protegido también requiere token válido."""
        assert client.delete("/envios/LT-00000001").status_code == 401


# ── CA-5: Token expirado devuelve 401 ────────────────────────────────────────

class TestCA5TokenExpirado:

    def test_token_expirado_retorna_401_en_get(self, client, headers_operador):
        """CA-5 — Token con exp en el pasado → 401 Unauthorized."""
        headers = {"Authorization": f"Bearer {_token_expirado()}"}
        assert client.get("/envios/", headers=headers).status_code == 401

    def test_token_expirado_retorna_401_en_post(self, client, headers_operador):
        """CA-5 — Token expirado en POST protegido → 401."""
        headers = {"Authorization": f"Bearer {_token_expirado()}"}
        assert client.post("/usuarios", json={}, headers=headers).status_code == 401

    def test_token_expirado_retorna_401_en_logout(self, client, headers_operador):
        """CA-5 — Token expirado en logout → 401."""
        headers = {"Authorization": f"Bearer {_token_expirado()}"}
        assert client.post("/auth/logout", headers=headers).status_code == 401


# ── CA-6: Token con firma inválida devuelve 401 ───────────────────────────────

class TestCA6TokenFirmaInvalida:

    def test_firma_incorrecta_retorna_401_en_get(self, client, headers_operador):
        """CA-6 — Token firmado con clave errónea → 401 Unauthorized."""
        headers = {"Authorization": f"Bearer {_token_firma_invalida()}"}
        assert client.get("/envios/", headers=headers).status_code == 401

    def test_firma_incorrecta_retorna_401_en_delete(self, client, headers_operador):
        """CA-6 — Token con firma manipulada en DELETE → 401."""
        headers = {"Authorization": f"Bearer {_token_firma_invalida()}"}
        assert client.delete("/envios/LT-00000001", headers=headers).status_code == 401

    def test_token_sin_firma_retorna_401(self, client):
        """CA-6 — String que no es un JWT válido → 401."""
        headers = {"Authorization": "Bearer header.payload.firma_invalida"}
        assert client.get("/envios/", headers=headers).status_code == 401


# ── CA-7: Rol insuficiente devuelve 403 ──────────────────────────────────────

class TestCA7RolInsuficiente:

    def test_operador_en_endpoint_exclusivo_de_supervisor_retorna_403(
        self, client, headers_operador, headers_supervisor
    ):
        """CA-7 — Operador intenta DELETE (solo Supervisor) → 403 Forbidden."""
        from datetime import date, timedelta
        fecha_futura = str(date.today() + timedelta(days=30))
        payload = {
            "remitente": "Remitente Test",
            "destinatario": "Destinatario Test",
            "probabilidad_retraso": 0.5,
            "fecha_entrega_estimada": fecha_futura,
            "direccion_origen": {
                "calle": "Av. Corrientes", "numero": "1234",
                "ciudad": "Buenos Aires", "provincia": "Buenos Aires",
                "codigo_postal": "1043",
            },
            "direccion_destino": {
                "calle": "San Martín", "numero": "567",
                "ciudad": "Córdoba", "provincia": "Córdoba",
                "codigo_postal": "5000",
            },
        }
        r = client.post("/envios/", json=payload, headers=headers_operador)
        tid = r.json()["tracking_id"]
        assert client.delete(f"/envios/{tid}", headers=headers_operador).status_code == 403

    def test_admin_en_endpoint_de_envios_retorna_403(self, client, headers_admin):
        """CA-7 — Admin intenta acceder a GET /envios/ (solo Operador/Supervisor) → 403."""
        assert client.get("/envios/", headers=headers_admin).status_code == 403


# ── CA-8: Request sin token devuelve 401 ─────────────────────────────────────

class TestCA8SinToken:

    def test_get_envios_sin_token_retorna_401(self, client):
        """CA-8 — GET /envios/ sin Authorization → 401."""
        assert client.get("/envios/").status_code == 401

    def test_post_envios_sin_token_retorna_401(self, client):
        """CA-8 — POST /envios/ sin Authorization → 401."""
        assert client.post("/envios/", json={}).status_code == 401

    def test_post_usuarios_sin_token_retorna_401(self, client):
        """CA-8 — POST /usuarios sin Authorization → 401."""
        assert client.post("/usuarios", json={}).status_code == 401

    def test_delete_envio_sin_token_retorna_401(self, client):
        """CA-8 — DELETE /envios/{id} sin Authorization → 401."""
        assert client.delete("/envios/LT-00000001").status_code == 401

    def test_logout_sin_token_retorna_401(self, client):
        """CA-8 — POST /auth/logout sin Authorization → 401."""
        assert client.post("/auth/logout").status_code == 401

    def test_auditoria_sin_token_retorna_401(self, client):
        """CA-8 — GET /auditoria/eventos sin Authorization → 401."""
        assert client.get("/auditoria/eventos").status_code == 401


# ── CA-9: SECRET_KEY desde variable de entorno ───────────────────────────────

class TestCA9SecretKeyDesdeEntorno:

    def test_auth_module_lee_secret_key_desde_os_getenv(self):
        """CA-9 (NFR) — El módulo auth.py lee la SECRET_KEY exclusivamente desde os.getenv."""
        src_path = pathlib.Path(__file__).parent.parent / "auth.py"
        contenido = src_path.read_text(encoding="utf-8")
        assert 'os.getenv("SECRET_KEY"' in contenido or 'os.environ' in contenido, (
            "SECRET_KEY debe leerse desde variable de entorno, no estar hardcodeada"
        )

    def test_token_firmado_con_clave_erronea_es_rechazado(self, client, headers_operador):
        """CA-9 — Un token firmado con clave distinta a la del servidor es rechazado (valida que la clave es efectiva)."""
        token_clave_erronea = _token_firma_invalida()
        headers = {"Authorization": f"Bearer {token_clave_erronea}"}
        assert client.get("/envios/", headers=headers).status_code == 401
