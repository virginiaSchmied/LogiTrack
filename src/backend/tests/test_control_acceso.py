"""
Tests unitarios para la diferenciación de acceso a funcionalidades según el rol.

Historia: Como sistema, quiero que cada rol tenga acceso exclusivamente a las
funcionalidades que le corresponden, sin posibilidad de escalada de privilegios.

Roles del sistema: OPERADOR — SUPERVISOR — ADMINISTRADOR

Criterios de Aceptación cubiertos:
  CA-1 — Operador no puede ejecutar acciones exclusivas de Supervisor
          (eliminación lógica, estados de excepción)
  CA-2 — Operador no puede acceder a auditoría de usuarios
  CA-3 — Administrador no puede acceder a funcionalidades de envíos
  CA-4 — Supervisor no puede gestionar usuarios
  CA-5 — Validación centralizada en backend (cada endpoint verifica el rol)
  CA-6 — Protección independiente de la UI (acceso directo por API también denegado)
  CA-7 — Mensaje de error controlado (403 con mensaje claro, sin detalles internos)
  CA-8 — Operador no puede gestionar usuarios
"""
from datetime import date, timedelta

_FECHA_FUTURA = str(date.today() + timedelta(days=30))

_PAYLOAD_ENVIO = {
    "remitente": "Juan Pérez",
    "destinatario": "María García",
    "probabilidad_retraso": 0.5,
    "fecha_entrega_estimada": _FECHA_FUTURA,
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

_PAYLOAD_USUARIO = {
    "email": "nuevo_usuario@logitrack.com",
    "password": "Segura1234!",
    "rol_nombre": "OPERADOR",
}


def _crear_envio(client, headers) -> str:
    """Crea un envío con el token dado y devuelve su tracking_id."""
    r = client.post("/envios/", json=_PAYLOAD_ENVIO, headers=headers)
    assert r.status_code == 201, f"No se pudo crear el envío: {r.text}"
    return r.json()["tracking_id"]


# ── CA-1: Operador no puede ejecutar acciones de Supervisor ──────────────────

class TestCA1OperadorNoEjecutaAccionesDeSupervisor:

    def test_operador_no_puede_eliminar_envio_retorna_403(
        self, client, headers_operador, headers_supervisor
    ):
        """CA-1 — Operador en DELETE /envios/{id} → 403 Forbidden."""
        tid = _crear_envio(client, headers_operador)
        assert client.delete(f"/envios/{tid}", headers=headers_operador).status_code == 403

    def test_operador_no_puede_asignar_estado_retrasado_retorna_403(
        self, client, headers_operador
    ):
        """CA-1 — Operador intentando poner estado RETRASADO (excepción) → 403."""
        tid = _crear_envio(client, headers_operador)
        # Primero avanzar al estado EN_DEPOSITO (válido para operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "nueva_ubicacion": {
                "calle": "Mitre", "numero": "100",
                "ciudad": "Rosario", "provincia": "Santa Fe",
                "codigo_postal": "2000",
            },
        }, headers=headers_operador)
        # Operador intenta asignar RETRASADO (exclusivo de supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "nueva_ubicacion": {
                "calle": "Belgrano", "numero": "200",
                "ciudad": "Mendoza", "provincia": "Mendoza",
                "codigo_postal": "5500",
            },
        }, headers=headers_operador)
        assert resp.status_code == 403

    def test_operador_no_puede_asignar_estado_bloqueado_retorna_403(
        self, client, headers_operador
    ):
        """CA-1 — Operador intentando poner estado BLOQUEADO (excepción) → 403."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "nueva_ubicacion": {
                "calle": "Mitre", "numero": "100",
                "ciudad": "Rosario", "provincia": "Santa Fe",
                "codigo_postal": "2000",
            },
        }, headers=headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "BLOQUEADO",
            "nueva_ubicacion": {
                "calle": "Belgrano", "numero": "200",
                "ciudad": "Mendoza", "provincia": "Mendoza",
                "codigo_postal": "5500",
            },
        }, headers=headers_operador)
        assert resp.status_code == 403

    def test_supervisor_si_puede_eliminar_envio(
        self, client, headers_operador, headers_supervisor
    ):
        """CA-1 (complementario) — Supervisor puede eliminar un envío → 200."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        assert client.delete(f"/envios/{tid}", headers=headers_supervisor).status_code == 200

    def test_supervisor_si_puede_asignar_estado_retrasado(
        self, client, headers_operador, headers_supervisor
    ):
        """CA-1 (complementario) — Supervisor puede asignar estado de excepción → no 403."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "nueva_ubicacion": {
                "calle": "Mitre", "numero": "100",
                "ciudad": "Rosario", "provincia": "Santa Fe",
                "codigo_postal": "2000",
            },
        }, headers=headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "nueva_ubicacion": {
                "calle": "Belgrano", "numero": "200",
                "ciudad": "Mendoza", "provincia": "Mendoza",
                "codigo_postal": "5500",
            },
        }, headers=headers_supervisor)
        assert resp.status_code != 403


# ── CA-2: Operador no puede acceder a auditoría de usuarios ──────────────────

class TestCA2OperadorNoAccedeAuditoria:

    def test_operador_no_puede_ver_auditoria_de_usuarios_retorna_403(
        self, client, headers_operador
    ):
        """CA-2 — GET /auditoria/eventos con rol Operador → 403 Forbidden."""
        assert client.get("/auditoria/eventos", headers=headers_operador).status_code == 403

    def test_operador_con_filtro_tampoco_puede_ver_auditoria(
        self, client, headers_operador
    ):
        """CA-2 — Operador con filtros en auditoría → sigue siendo 403."""
        resp = client.get(
            "/auditoria/eventos?usuario_afectado_uuid=algún-uuid",
            headers=headers_operador,
        )
        assert resp.status_code == 403


# ── CA-3: Administrador no puede acceder a funcionalidades de envíos ─────────

class TestCA3AdminNoAccedeEnvios:

    def test_admin_no_puede_listar_envios_retorna_403(self, client, headers_admin):
        """CA-3 — Admin en GET /envios/ → 403 Forbidden."""
        assert client.get("/envios/", headers=headers_admin).status_code == 403

    def test_admin_no_puede_crear_envio_retorna_403(self, client, headers_admin):
        """CA-3 — Admin en POST /envios/ → 403 Forbidden."""
        assert client.post("/envios/", json=_PAYLOAD_ENVIO, headers=headers_admin).status_code == 403

    def test_admin_no_puede_eliminar_envio_retorna_403(self, client, headers_admin):
        """CA-3 — Admin en DELETE /envios/{id} → 403 Forbidden."""
        assert client.delete("/envios/LT-00000001", headers=headers_admin).status_code == 403

    def test_admin_no_puede_editar_contacto_de_envio_retorna_403(
        self, client, headers_admin
    ):
        """CA-3 — Admin en PATCH /envios/{id}/contacto → 403 Forbidden."""
        resp = client.patch("/envios/LT-00000001/contacto", json={
            "destinatario": "Otro",
            "direccion_destino": {
                "calle": "San Martín", "numero": "1",
                "ciudad": "Córdoba", "provincia": "Córdoba",
                "codigo_postal": "5000",
            },
        }, headers=headers_admin)
        assert resp.status_code == 403

    def test_admin_no_puede_cambiar_estado_de_envio_retorna_403(
        self, client, headers_admin
    ):
        """CA-3 — Admin en PATCH /envios/{id}/estado → 403 Forbidden."""
        resp = client.patch("/envios/LT-00000001/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
        }, headers=headers_admin)
        assert resp.status_code == 403

    def test_admin_si_puede_acceder_a_auditoria_de_usuarios(self, client, headers_admin):
        """CA-3 (complementario) — Admin puede acceder a /auditoria/eventos → 200."""
        assert client.get("/auditoria/eventos", headers=headers_admin).status_code == 200


# ── CA-4: Supervisor no puede gestionar usuarios ─────────────────────────────

class TestCA4SupervisorNoGestionaUsuarios:

    def test_supervisor_no_puede_registrar_usuario_retorna_403(
        self, client, headers_supervisor
    ):
        """CA-4 — Supervisor en POST /usuarios → 403 Forbidden."""
        assert client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_supervisor).status_code == 403

    def test_supervisor_no_puede_ver_auditoria_de_usuarios_retorna_403(
        self, client, headers_supervisor
    ):
        """CA-4 — Supervisor en GET /auditoria/eventos → 403 Forbidden."""
        assert client.get("/auditoria/eventos", headers=headers_supervisor).status_code == 403

    def test_supervisor_si_puede_acceder_a_envios(self, client, headers_supervisor):
        """CA-4 (complementario) — Supervisor puede acceder a funcionalidades de envíos → 200."""
        assert client.get("/envios/", headers=headers_supervisor).status_code == 200


# ── CA-5: Validación centralizada en backend ─────────────────────────────────

class TestCA5ValidacionCentralizadaBackend:

    def test_validacion_de_rol_ocurre_antes_de_ejecutar_logica(
        self, client, db_session, headers_operador
    ):
        """CA-5 — El 403 se retorna antes de ejecutar la lógica: el usuario no es creado."""
        from models import Usuario
        resp = client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador)
        assert resp.status_code == 403
        usuario = db_session.query(Usuario).filter(
            Usuario.email == _PAYLOAD_USUARIO["email"]
        ).first()
        assert usuario is None

    def test_validacion_aplica_a_todos_los_metodos_http(
        self, client, headers_operador
    ):
        """CA-5 — La validación no depende del método HTTP: POST y DELETE también son bloqueados."""
        assert client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador).status_code == 403
        assert client.delete("/envios/LT-99999999", headers=headers_operador).status_code == 403


# ── CA-6: Protección independiente de la UI ──────────────────────────────────

class TestCA6ProteccionIndependienteUI:

    def test_acceso_directo_por_api_a_endpoint_de_admin_es_denegado(
        self, client, headers_operador
    ):
        """CA-6 — Acceso directo por API a /usuarios sin rol Admin → 403, sin importar la UI."""
        assert client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador).status_code == 403

    def test_acceso_directo_por_api_a_auditoria_es_denegado_para_operador(
        self, client, headers_operador
    ):
        """CA-6 — Acceso directo a /auditoria/eventos con rol Operador → 403."""
        assert client.get("/auditoria/eventos", headers=headers_operador).status_code == 403

    def test_acceso_directo_por_api_a_envios_es_denegado_para_admin(
        self, client, headers_admin
    ):
        """CA-6 — Acceso directo a /envios/ con rol Administrador → 403."""
        assert client.get("/envios/", headers=headers_admin).status_code == 403


# ── CA-7: Mensaje de error controlado ────────────────────────────────────────

class TestCA7MensajeErrorControlado:

    def test_403_incluye_campo_detail(self, client, headers_operador):
        """CA-7 — La respuesta 403 incluye el campo 'detail' con un mensaje."""
        resp = client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador)
        assert resp.status_code == 403
        assert "detail" in resp.json()

    def test_403_no_expone_stack_trace(self, client, headers_operador):
        """CA-7 — La respuesta 403 no expone traza de error interno (stack trace)."""
        resp = client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador)
        body_str = str(resp.json())
        assert "Traceback" not in body_str
        assert "Exception" not in body_str
        assert "File " not in body_str

    def test_403_mensaje_es_legible(self, client, headers_operador):
        """CA-7 — El mensaje de error 403 es legible y no expone detalles de implementación."""
        resp = client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador)
        assert resp.status_code == 403
        detail = resp.json().get("detail", "")
        # El mensaje debe ser una cadena no vacía y comprensible
        assert isinstance(detail, str)
        assert len(detail) > 0

    def test_401_incluye_campo_detail(self, client):
        """CA-7 (complementario) — La respuesta 401 también incluye 'detail' descriptivo."""
        resp = client.get("/envios/")
        assert resp.status_code == 401
        assert "detail" in resp.json()


# ── CA-8: Operador no puede gestionar usuarios ───────────────────────────────

class TestCA8OperadorNoGestionaUsuarios:

    def test_operador_no_puede_registrar_usuario_retorna_403(
        self, client, headers_operador
    ):
        """CA-8 — Operador en POST /usuarios → 403 Forbidden."""
        assert client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_operador).status_code == 403

    def test_operador_no_puede_ver_auditoria_usuarios_retorna_403(
        self, client, headers_operador
    ):
        """CA-8 — Operador en GET /auditoria/eventos → 403 Forbidden."""
        assert client.get("/auditoria/eventos", headers=headers_operador).status_code == 403

    def test_operador_no_puede_registrar_usuario_con_cualquier_email(
        self, client, headers_operador
    ):
        """CA-8 — El 403 no depende del payload: cualquier intento de registro es bloqueado."""
        for email in ["a@b.com", "admin@empresa.com", "root@sistema.com"]:
            payload = {**_PAYLOAD_USUARIO, "email": email}
            assert client.post("/usuarios", json=payload, headers=headers_operador).status_code == 403

    def test_admin_si_puede_registrar_usuario(self, client, headers_admin):
        """CA-8 (complementario) — Solo el Administrador puede crear usuarios → 201."""
        assert client.post("/usuarios", json=_PAYLOAD_USUARIO, headers=headers_admin).status_code == 201
