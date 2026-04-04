"""
Tests unitarios para el registro de nuevos usuarios.

Historia: Como administrador, quiero registrar nuevos usuarios en el sistema
asignándoles un rol, para que puedan operar dentro de sus permisos correspondientes.

Endpoint: POST /usuarios  — requiere rol ADMINISTRADOR.

Criterios de Aceptación cubiertos:
  CA-1 (NFR) — Contraseñas no almacenadas en texto plano
  CA-2       — Registro exitoso de un usuario
  CA-3       — Email único por usuario
  CA-4       — Rol obligatorio al registrar
  CA-5       — Validación de campos obligatorios
  CA-6       — Contraseña almacenada como hash bcrypt
  CA-7       — Solo roles válidos pueden asignarse
"""

from models import Usuario

_PAYLOAD_VALIDO = {
    "email": "nuevo@logitrack.com",
    "password": "Segura1234!",
    "rol_nombre": "OPERADOR",
}


# ── Control de acceso al endpoint ────────────────────────────────────────────

class TestControlAccesoRegistro:

    def test_sin_token_retorna_401(self, client):
        """Sin header Authorization → 401 Unauthorized."""
        assert client.post("/usuarios", json=_PAYLOAD_VALIDO).status_code == 401

    def test_token_invalido_retorna_401(self, client):
        """Token con firma inválida → 401 Unauthorized."""
        headers = {"Authorization": "Bearer token.invalido.aqui"}
        assert client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers).status_code == 401

    def test_operador_no_puede_registrar_usuarios_retorna_403(self, client, headers_operador):
        """Operador intenta crear usuario → 403 Forbidden."""
        assert client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_operador).status_code == 403

    def test_supervisor_no_puede_registrar_usuarios_retorna_403(self, client, headers_supervisor):
        """Supervisor intenta crear usuario → 403 Forbidden."""
        assert client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_supervisor).status_code == 403


# ── CA-2: Registro exitoso ────────────────────────────────────────────────────

class TestCA2RegistroExitoso:

    def test_admin_con_datos_validos_retorna_201(self, client, headers_admin):
        """CA-2 — Admin + datos válidos → 201 Created."""
        resp = client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        assert resp.status_code == 201

    def test_respuesta_incluye_email_del_usuario(self, client, headers_admin):
        """CA-2 — La respuesta expone el email del usuario registrado."""
        resp = client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        assert resp.status_code == 201
        assert resp.json()["email"] == _PAYLOAD_VALIDO["email"]

    def test_respuesta_incluye_rol_asignado(self, client, headers_admin):
        """CA-2 — La respuesta expone el rol asignado al nuevo usuario."""
        resp = client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        assert resp.status_code == 201
        assert resp.json()["nombre_rol"] == _PAYLOAD_VALIDO["rol_nombre"]

    def test_respuesta_incluye_uuid_del_usuario(self, client, headers_admin):
        """CA-2 — La respuesta expone el UUID generado para el nuevo usuario."""
        resp = client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        assert resp.status_code == 201
        assert "uuid" in resp.json()
        assert resp.json()["uuid"] != ""

    def test_usuario_registrado_puede_autenticarse(self, client, headers_admin):
        """CA-2 — El usuario registrado puede hacer login con sus credenciales."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        login_resp = client.post("/auth/login", json={
            "email": _PAYLOAD_VALIDO["email"],
            "password": _PAYLOAD_VALIDO["password"],
        })
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()

    def test_usuario_registrado_persiste_en_base_de_datos(self, client, db_session, headers_admin):
        """CA-2 — El usuario queda guardado en la base de datos."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        usuario = db_session.query(Usuario).filter(
            Usuario.email == _PAYLOAD_VALIDO["email"]
        ).first()
        assert usuario is not None


# ── CA-3: Email único por usuario ─────────────────────────────────────────────

class TestCA3EmailUnico:

    def test_email_duplicado_retorna_409(self, client, headers_admin):
        """CA-3 — Segundo registro con el mismo email → 409 Conflict."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        resp = client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        assert resp.status_code == 409

    def test_email_duplicado_no_crea_segundo_registro(self, client, db_session, headers_admin):
        """CA-3 — Tras intentar duplicar, solo existe un registro en BD."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        count = db_session.query(Usuario).filter(
            Usuario.email == _PAYLOAD_VALIDO["email"]
        ).count()
        assert count == 1

    def test_email_duplicado_respuesta_incluye_mensaje_de_error(self, client, headers_admin):
        """CA-3 — La respuesta de 409 incluye un mensaje descriptivo."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        resp = client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        assert resp.status_code == 409
        assert "detail" in resp.json()

    def test_email_diferente_permite_segundo_registro(self, client, headers_admin):
        """CA-3 — Emails distintos → ambos registros son aceptados."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        payload2 = {**_PAYLOAD_VALIDO, "email": "otro@logitrack.com"}
        resp = client.post("/usuarios", json=payload2, headers=headers_admin)
        assert resp.status_code == 201

    def test_email_case_insensitive_detecta_duplicado(self, client, headers_admin):
        """CA-3 — El email en mayúsculas se trata igual que en minúsculas (no se permiten duplicados)."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        payload_upper = {**_PAYLOAD_VALIDO, "email": _PAYLOAD_VALIDO["email"].upper()}
        resp = client.post("/usuarios", json=payload_upper, headers=headers_admin)
        assert resp.status_code == 409


# ── CA-4: Rol obligatorio ─────────────────────────────────────────────────────

class TestCA4RolObligatorio:

    def test_sin_campo_rol_retorna_422(self, client, headers_admin):
        """CA-4 — Payload sin rol_nombre → 422 Unprocessable Entity."""
        payload = {"email": "x@logitrack.com", "password": "Segura1234!"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 422

    def test_rol_cadena_vacia_retorna_422(self, client, headers_admin):
        """CA-4 — rol_nombre vacío → 422 (no es un rol válido del sistema)."""
        payload = {**_PAYLOAD_VALIDO, "rol_nombre": ""}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 422

    def test_error_422_especifica_campo_rol(self, client, headers_admin):
        """CA-4 — El error 422 menciona el campo rol_nombre."""
        payload = {"email": "x@logitrack.com", "password": "Segura1234!"}
        resp = client.post("/usuarios", json=payload, headers=headers_admin)
        assert resp.status_code == 422
        campos = [str(e.get("loc", "")) for e in resp.json()["detail"]]
        assert any("rol_nombre" in c for c in campos)


# ── CA-5: Validación de campos obligatorios ───────────────────────────────────

class TestCA5CamposObligatorios:

    def test_sin_email_retorna_422(self, client, headers_admin):
        """CA-5 — Payload sin email → 422."""
        payload = {"password": "Segura1234!", "rol_nombre": "OPERADOR"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 422

    def test_email_formato_invalido_retorna_422(self, client, headers_admin):
        """CA-5 — Email sin formato válido → 422."""
        payload = {**_PAYLOAD_VALIDO, "email": "no-es-un-email"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 422

    def test_sin_password_retorna_422(self, client, headers_admin):
        """CA-5 — Payload sin password → 422."""
        payload = {"email": "x@logitrack.com", "rol_nombre": "OPERADOR"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 422

    def test_password_menor_a_8_caracteres_retorna_422(self, client, headers_admin):
        """CA-5 — Contraseña de menos de 8 caracteres → 422."""
        payload = {**_PAYLOAD_VALIDO, "password": "corta"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 422

    def test_payload_completamente_vacio_retorna_422(self, client, headers_admin):
        """CA-5 — Payload vacío → 422 con detalle de los campos faltantes."""
        resp = client.post("/usuarios", json={}, headers=headers_admin)
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_error_422_incluye_detalle_del_campo_faltante(self, client, headers_admin):
        """CA-5 — El cuerpo del error 422 lista los campos con problema."""
        payload = {"rol_nombre": "OPERADOR"}
        resp = client.post("/usuarios", json=payload, headers=headers_admin)
        assert resp.status_code == 422
        campos = [str(e.get("loc", "")) for e in resp.json()["detail"]]
        assert any("email" in c for c in campos)


# ── CA-6 / CA-1 (NFR): Hash de contraseña ────────────────────────────────────

class TestCA6CA1HashContrasena:

    def test_contrasena_no_almacenada_en_texto_plano(self, client, db_session, headers_admin):
        """CA-1/CA-6 — El hash en BD es distinto a la contraseña original."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        usuario = db_session.query(Usuario).filter(
            Usuario.email == _PAYLOAD_VALIDO["email"]
        ).first()
        assert usuario is not None
        assert usuario.contrasena_hash != _PAYLOAD_VALIDO["password"]

    def test_hash_almacenado_verifica_la_contrasena_original(self, client, db_session, headers_admin):
        """CA-6 — El hash almacenado es válido: permite verificar la contraseña original con bcrypt."""
        from auth import verify_password
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        usuario = db_session.query(Usuario).filter(
            Usuario.email == _PAYLOAD_VALIDO["email"]
        ).first()
        assert verify_password(_PAYLOAD_VALIDO["password"], usuario.contrasena_hash)

    def test_hash_tiene_prefijo_bcrypt(self, client, db_session, headers_admin):
        """CA-6 — El hash almacenado comienza con el prefijo bcrypt ($2b$ o $2a$)."""
        client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        usuario = db_session.query(Usuario).filter(
            Usuario.email == _PAYLOAD_VALIDO["email"]
        ).first()
        assert usuario.contrasena_hash.startswith("$2")

    def test_respuesta_no_expone_la_contrasena(self, client, headers_admin):
        """CA-1 — La respuesta del endpoint no expone el campo password ni el hash."""
        resp = client.post("/usuarios", json=_PAYLOAD_VALIDO, headers=headers_admin)
        assert resp.status_code == 201
        body = resp.json()
        assert "password" not in body
        assert "contrasena_hash" not in body


# ── CA-7: Solo roles válidos pueden asignarse ─────────────────────────────────

class TestCA7RolesValidos:

    def test_rol_desconocido_retorna_422(self, client, headers_admin):
        """CA-7 — Rol fuera del conjunto definido → 422."""
        payload = {**_PAYLOAD_VALIDO, "rol_nombre": "GERENTE"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 422

    def test_rol_numerico_retorna_422(self, client, headers_admin):
        """CA-7 — Valor numérico como rol → 422."""
        payload = {**_PAYLOAD_VALIDO, "email": "x1@logitrack.com", "rol_nombre": "1"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 422

    def test_rol_operador_es_aceptado(self, client, headers_admin):
        """CA-7 — OPERADOR es un rol válido del sistema → 201."""
        payload = {**_PAYLOAD_VALIDO, "rol_nombre": "OPERADOR"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 201

    def test_rol_supervisor_es_aceptado(self, client, headers_admin):
        """CA-7 — SUPERVISOR es un rol válido del sistema → 201."""
        payload = {**_PAYLOAD_VALIDO, "email": "sv@logitrack.com", "rol_nombre": "SUPERVISOR"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 201

    def test_rol_administrador_es_aceptado(self, client, headers_admin):
        """CA-7 — ADMINISTRADOR es un rol válido del sistema → 201."""
        payload = {**_PAYLOAD_VALIDO, "email": "adm2@logitrack.com", "rol_nombre": "ADMINISTRADOR"}
        assert client.post("/usuarios", json=payload, headers=headers_admin).status_code == 201

    def test_rol_invalido_no_persiste_usuario(self, client, db_session, headers_admin):
        """CA-7 — Con rol inválido no se crea ningún usuario en BD."""
        payload = {**_PAYLOAD_VALIDO, "email": "x2@logitrack.com", "rol_nombre": "FANTASMA"}
        client.post("/usuarios", json=payload, headers=headers_admin)
        usuario = db_session.query(Usuario).filter(
            Usuario.email == "x2@logitrack.com"
        ).first()
        assert usuario is None
