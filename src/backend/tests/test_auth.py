"""
Tests para el módulo auth.py y los endpoints /auth/login y /auth/logout.

Cubre:
  - create_access_token: campos en el payload, firma HS256, expiración
  - decode_token: token válido, inválido, expirado, firma incorrecta (→ 401)
  - verify_password / hash_password
  - get_current_user: usuario activo / inactivo (→ 401)
  - _RequireRoles: token expirado, inválido, usuario inactivo (→ 401/403)
  - POST /auth/login: credenciales válidas, inválidas, usuario inactivo, case-insensitive, auditoría
  - POST /auth/logout: sesión activa, sin token, token inválido, auditoría
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

import models
from auth import (
    SECRET_KEY, ALGORITHM,
    create_access_token, decode_token,
    hash_password, verify_password,
)
from tests.conftest import (
    USUARIO_OPERADOR_UUID,
    USUARIO_SUPERVISOR_UUID,
    USUARIO_ADMIN_UUID,
)


# ── Utilidades: create_access_token ──────────────────────────────────────────

class TestCreateAccessToken:
    def test_contiene_sub_email_rol(self):
        token = create_access_token("uuid-1", "u@test.com", "OPERADOR")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "uuid-1"
        assert payload["email"] == "u@test.com"
        assert payload["rol"] == "OPERADOR"

    def test_contiene_iat_y_exp(self):
        token = create_access_token("uuid-1", "u@test.com", "OPERADOR")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] > payload["iat"]

    def test_exp_aproximadamente_8_horas(self):
        before = datetime.now(timezone.utc)
        token = create_access_token("uuid-1", "u@test.com", "OPERADOR")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = exp - before
        assert timedelta(hours=7, minutes=59) < delta < timedelta(hours=8, minutes=1)

    def test_tokens_distintos_por_usuario(self):
        t1 = create_access_token("uuid-1", "a@test.com", "OPERADOR")
        t2 = create_access_token("uuid-2", "b@test.com", "SUPERVISOR")
        assert t1 != t2


# ── Utilidades: decode_token ──────────────────────────────────────────────────

class TestDecodeToken:
    def test_token_valido_decodifica(self):
        token = create_access_token("uuid-99", "x@test.com", "SUPERVISOR")
        payload = decode_token(token)
        assert payload["sub"] == "uuid-99"
        assert payload["rol"] == "SUPERVISOR"

    def test_token_invalido_lanza_401(self):
        with pytest.raises(HTTPException) as exc:
            decode_token("token.invalido.firma")
        assert exc.value.status_code == 401

    def test_token_expirado_lanza_401(self):
        expired_payload = {
            "sub": "uuid-1",
            "email": "u@test.com",
            "rol": "OPERADOR",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=10)).timestamp()),
            "exp": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(HTTPException) as exc:
            decode_token(token)
        assert exc.value.status_code == 401

    def test_token_firma_incorrecta_lanza_401(self):
        token = jwt.encode(
            {"sub": "x", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            "clave-falsa",
            algorithm=ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            decode_token(token)
        assert exc.value.status_code == 401

    def test_detail_menciona_token_invalido(self):
        with pytest.raises(HTTPException) as exc:
            decode_token("garbage")
        assert "inválido" in exc.value.detail.lower() or "expirado" in exc.value.detail.lower()


# ── Utilidades: hash_password / verify_password ───────────────────────────────

class TestPasswordUtils:
    def test_hash_no_es_texto_plano(self):
        hashed = hash_password("MiClave123!")
        assert hashed != "MiClave123!"

    def test_hash_es_reproducible_con_verify(self):
        hashed = hash_password("MiClave123!")
        assert verify_password("MiClave123!", hashed) is True

    def test_password_incorrecta_no_verifica(self):
        hashed = hash_password("MiClave123!")
        assert verify_password("OtraClave!", hashed) is False

    def test_hashes_distintos_para_misma_clave(self):
        """bcrypt genera salt aleatorio → dos hashes distintos para la misma clave."""
        h1 = hash_password("MiClave123!")
        h2 = hash_password("MiClave123!")
        assert h1 != h2
        assert verify_password("MiClave123!", h1)
        assert verify_password("MiClave123!", h2)


# ── POST /auth/login ──────────────────────────────────────────────────────────

URL_LOGIN = "/auth/login"


class TestLogin:
    def test_login_exitoso_operador(self, client):
        res = client.post(URL_LOGIN, json={"email": "operador@test.com", "password": "test1234"})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["email"] == "operador@test.com"
        assert data["nombre_rol"] == "OPERADOR"
        assert data["token_type"] == "bearer"

    def test_login_exitoso_supervisor(self, client):
        res = client.post(URL_LOGIN, json={"email": "supervisor@test.com", "password": "test1234"})
        assert res.status_code == 200
        assert res.json()["nombre_rol"] == "SUPERVISOR"

    def test_login_exitoso_admin(self, client):
        res = client.post(URL_LOGIN, json={"email": "admin@test.com", "password": "test1234"})
        assert res.status_code == 200
        assert res.json()["nombre_rol"] == "ADMINISTRADOR"

    def test_token_contiene_campos_correctos(self, client):
        res = client.post(URL_LOGIN, json={"email": "operador@test.com", "password": "test1234"})
        assert res.status_code == 200
        token = res.json()["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == str(USUARIO_OPERADOR_UUID)
        assert payload["email"] == "operador@test.com"
        assert payload["rol"] == "OPERADOR"
        assert "exp" in payload
        assert "iat" in payload

    def test_email_incorrecto_retorna_401(self, client):
        res = client.post(URL_LOGIN, json={"email": "noexiste@test.com", "password": "test1234"})
        assert res.status_code == 401

    def test_password_incorrecta_retorna_401(self, client):
        res = client.post(URL_LOGIN, json={"email": "operador@test.com", "password": "wrongpass"})
        assert res.status_code == 401

    def test_mensaje_error_generico_no_revela_campo(self, client):
        """LP-21 CA-3: mismo mensaje de error para email inexistente y contraseña incorrecta."""
        res_email = client.post(URL_LOGIN, json={"email": "noexiste@test.com", "password": "test1234"})
        res_pass  = client.post(URL_LOGIN, json={"email": "operador@test.com", "password": "wrong"})
        assert res_email.json()["detail"] == res_pass.json()["detail"]

    def test_email_case_insensitive(self, client):
        res = client.post(URL_LOGIN, json={"email": "OPERADOR@TEST.COM", "password": "test1234"})
        assert res.status_code == 200

    def test_email_con_espacios_es_aceptado(self, client):
        res = client.post(URL_LOGIN, json={"email": "  operador@test.com  ", "password": "test1234"})
        assert res.status_code == 200

    def test_usuario_inactivo_retorna_401(self, client, db_session):
        usuario = (
            db_session.query(models.Usuario)
            .filter(models.Usuario.uuid == USUARIO_OPERADOR_UUID)
            .first()
        )
        usuario.estado = models.EstadoUsuarioEnum.BAJA
        db_session.commit()

        res = client.post(URL_LOGIN, json={"email": "operador@test.com", "password": "test1234"})
        assert res.status_code == 401

    def test_usuario_inactivo_mismo_mensaje_que_credenciales_invalidas(self, client, db_session):
        """LP-21 CA-3: usuario inactivo no debe revelar que la cuenta existe."""
        usuario = (
            db_session.query(models.Usuario)
            .filter(models.Usuario.uuid == USUARIO_OPERADOR_UUID)
            .first()
        )
        usuario.estado = models.EstadoUsuarioEnum.BAJA
        db_session.commit()

        res_inactivo = client.post(URL_LOGIN, json={"email": "operador@test.com", "password": "test1234"})
        res_noexiste = client.post(URL_LOGIN, json={"email": "noexiste@test.com", "password": "test1234"})
        assert res_inactivo.json()["detail"] == res_noexiste.json()["detail"]

    def test_evento_login_registrado(self, client, db_session):
        client.post(URL_LOGIN, json={"email": "operador@test.com", "password": "test1234"})
        evento = (
            db_session.query(models.EventoDeUsuario)
            .filter(
                models.EventoDeUsuario.usuario_afectado_uuid == USUARIO_OPERADOR_UUID,
                models.EventoDeUsuario.accion == models.AccionUsuarioEnum.LOGIN,
            )
            .first()
        )
        assert evento is not None
        assert evento.usuario_ejecutor_uuid == USUARIO_OPERADOR_UUID

    def test_campos_faltantes_retorna_422(self, client):
        res = client.post(URL_LOGIN, json={"email": "operador@test.com"})
        assert res.status_code == 422

    def test_payload_vacio_retorna_422(self, client):
        res = client.post(URL_LOGIN, json={})
        assert res.status_code == 422


# ── POST /auth/logout ─────────────────────────────────────────────────────────

URL_LOGOUT = "/auth/logout"


class TestLogout:
    def test_logout_exitoso_operador(self, client, headers_operador):
        res = client.post(URL_LOGOUT, headers=headers_operador)
        assert res.status_code == 200
        assert "message" in res.json()

    def test_logout_exitoso_supervisor(self, client, headers_supervisor):
        res = client.post(URL_LOGOUT, headers=headers_supervisor)
        assert res.status_code == 200

    def test_logout_exitoso_admin(self, client, headers_admin):
        res = client.post(URL_LOGOUT, headers=headers_admin)
        assert res.status_code == 200

    def test_logout_sin_token_retorna_401_o_403(self, client):
        res = client.post(URL_LOGOUT)
        assert res.status_code in (401, 403)

    def test_logout_token_invalido_retorna_401(self, client):
        res = client.post(URL_LOGOUT, headers={"Authorization": "Bearer token.invalido"})
        assert res.status_code == 401

    def test_logout_token_expirado_retorna_401(self, client):
        expired_payload = {
            "sub": str(USUARIO_OPERADOR_UUID),
            "email": "operador@test.com",
            "rol": "OPERADOR",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=10)).timestamp()),
            "exp": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        res = client.post(URL_LOGOUT, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

    def test_evento_logout_registrado(self, client, headers_operador, db_session):
        client.post(URL_LOGOUT, headers=headers_operador)
        evento = (
            db_session.query(models.EventoDeUsuario)
            .filter(
                models.EventoDeUsuario.usuario_afectado_uuid == USUARIO_OPERADOR_UUID,
                models.EventoDeUsuario.accion == models.AccionUsuarioEnum.LOGOUT,
            )
            .first()
        )
        assert evento is not None
        assert evento.usuario_ejecutor_uuid == USUARIO_OPERADOR_UUID


# ── get_current_user: usuario inactivo ───────────────────────────────────────

class TestGetCurrentUserInactivo:
    """
    Verifica que get_current_user rechace tokens válidos de usuarios en estado BAJA.
    Se usa /auth/logout como endpoint proxy (cualquier ruta protegida sirve).
    """

    def test_usuario_inactivo_con_token_valido_retorna_401(self, client, db_session):
        usuario = (
            db_session.query(models.Usuario)
            .filter(models.Usuario.uuid == USUARIO_OPERADOR_UUID)
            .first()
        )
        usuario.estado = models.EstadoUsuarioEnum.BAJA
        db_session.commit()

        # El token en sí es válido (firmado correctamente), pero el usuario está dado de baja
        token = create_access_token(str(USUARIO_OPERADOR_UUID), "operador@test.com", "OPERADOR")
        res = client.post(URL_LOGOUT, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401


# ── _RequireRoles: control de acceso por rol ──────────────────────────────────

class TestRequireRoles:
    """
    Verifica que las dependencias de autorización bloqueen correctamente.
    Se usa POST /usuarios (require_admin) como endpoint proxy.
    """
    URL = "/usuarios"
    _PAYLOAD = {"email": "nuevo@test.com", "password": "Segura1234!", "rol_nombre": "OPERADOR"}

    def test_admin_accede_a_endpoint_exclusivo_admin(self, client, headers_admin):
        res = client.post(self.URL, json=self._PAYLOAD, headers=headers_admin)
        assert res.status_code == 201

    def test_operador_bloqueado_en_endpoint_admin_retorna_403(self, client, headers_operador):
        res = client.post(self.URL, json=self._PAYLOAD, headers=headers_operador)
        assert res.status_code == 403

    def test_supervisor_bloqueado_en_endpoint_admin_retorna_403(self, client, headers_supervisor):
        res = client.post(self.URL, json=self._PAYLOAD, headers=headers_supervisor)
        assert res.status_code == 403

    def test_sin_token_retorna_401_o_403(self, client):
        res = client.post(self.URL, json=self._PAYLOAD)
        assert res.status_code in (401, 403)

    def test_token_invalido_retorna_401(self, client):
        res = client.post(self.URL, json=self._PAYLOAD, headers={"Authorization": "Bearer xxx"})
        assert res.status_code == 401

    def test_token_expirado_retorna_401(self, client):
        expired_payload = {
            "sub": str(USUARIO_ADMIN_UUID),
            "email": "admin@test.com",
            "rol": "ADMINISTRADOR",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=10)).timestamp()),
            "exp": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        res = client.post(
            self.URL,
            json=self._PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 401

    def test_usuario_inactivo_con_token_valido_retorna_401(self, client, db_session):
        usuario = (
            db_session.query(models.Usuario)
            .filter(models.Usuario.uuid == USUARIO_ADMIN_UUID)
            .first()
        )
        usuario.estado = models.EstadoUsuarioEnum.BAJA
        db_session.commit()

        token = create_access_token(str(USUARIO_ADMIN_UUID), "admin@test.com", "ADMINISTRADOR")
        res = client.post(
            self.URL,
            json=self._PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 401
