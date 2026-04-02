"""
Tests para la auditoría de acciones sobre un envío.

Cubre:
  LP-174 — Consultar historial de acciones sobre un envío (supervisor)

  CP-0241 (HP)  — CA-3: Datos de cada entrada del historial
  CP-0242 (HP)  — CA-4: Historial incluye todas las acciones definidas
  CP-0243 (HP)  — CA-5: Historial de envío sin acciones adicionales (solo CREACION)
  CP-0244 (HP)  — CA-6: Registros no modificables (solo lectura)
  CP-0245 (HP)  — CA-7: Acceso sin autenticación devuelve 200 (auth pendiente)

Tests NO implementados (requieren JWT y control de roles):
  CP-0238 — CA-2: JWT rol = Supervisor → lista completa de acciones
  CP-0239 — CA-1: JWT rol = Operador → 403
  CP-0246 — CA-7: Sin Authorization → 401 y redirige a login
"""
from datetime import date, timedelta

_FECHA_FUTURA = str(date.today() + timedelta(days=30))

PAYLOAD_ENVIO = {
    "remitente": "Juan Pérez",
    "destinatario": "María García",
    "probabilidad_retraso": 0.5,
    "fecha_entrega_estimada": _FECHA_FUTURA,
    "direccion_origen": {
        "calle": "Av. Corrientes", "numero": "1234",
        "ciudad": "Buenos Aires", "provincia": "Buenos Aires", "codigo_postal": "1043",
    },
    "direccion_destino": {
        "calle": "San Martín", "numero": "567",
        "ciudad": "Córdoba", "provincia": "Córdoba", "codigo_postal": "5000",
    },
}

UBICACION = {
    "calle": "Mitre", "numero": "200",
    "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000",
}

CONTACTO_NUEVO = {
    "destinatario": "Carlos López",
    "direccion_destino": {
        "calle": "Belgrano", "numero": "100",
        "ciudad": "Mendoza", "provincia": "Mendoza", "codigo_postal": "5500",
    },
}


def _crear_envio(client) -> str:
    r = client.post("/envios/", json=PAYLOAD_ENVIO)
    assert r.status_code == 201
    return r.json()["tracking_id"]


def _get_auditoria(client, tid: str):
    return client.get(f"/envios/{tid}/auditoria")


# ── CP-0241 — CA-3: estructura de cada entrada ───────────────────────────────

class TestCP0241EstructuraEntradas:

    def test_cp0241_cada_entrada_tiene_accion_usuario_email_fecha(self, client):
        """CP-0241 (HP) — CA-3: Cada entrada tiene accion, usuario_email y fecha_hora."""
        tid = _crear_envio(client)
        entradas = _get_auditoria(client, tid).json()
        for entrada in entradas:
            assert "accion" in entrada
            assert "usuario_email" in entrada
            assert "fecha_hora" in entrada

    def test_cp0241_cada_entrada_tiene_estado_final(self, client):
        """CP-0241 (HP) — CA-3: Cada entrada expone el estado final al momento de la acción."""
        tid = _crear_envio(client)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION,
        })
        entradas = _get_auditoria(client, tid).json()
        for entrada in entradas:
            assert "estado_final" in entrada
            assert entrada["estado_final"] is not None

    def test_cp0241_endpoint_retorna_200(self, client):
        """CP-0241 (HP) — CA-3: El endpoint /auditoria responde 200."""
        tid = _crear_envio(client)
        assert _get_auditoria(client, tid).status_code == 200


# ── CP-0242 — CA-4: todas las acciones posibles ──────────────────────────────

class TestCP0242TodasLasAcciones:

    def test_cp0242_historial_incluye_todos_los_tipos_de_accion(self, client):
        """CP-0242 (HP) — CA-4: Auditoría incluye CREACION, MODIFICACION, MOVIMIENTO, CAMBIO_ESTADO y ELIMINACION."""
        tid = _crear_envio(client)

        # MODIFICACION: editar datos de contacto
        client.patch(f"/envios/{tid}/contacto", json=CONTACTO_NUEVO)

        # CAMBIO_ESTADO: REGISTRADO → EN_DEPOSITO
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION,
        })

        # MOVIMIENTO físico
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})

        # CAMBIO_ESTADO: EN_DEPOSITO → CANCELADO (no requiere ubicación)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"})

        # ELIMINACION lógica (requiere estado CANCELADO)
        client.delete(f"/envios/{tid}")

        entradas = _get_auditoria(client, tid).json()
        acciones = {e["accion"] for e in entradas}
        assert "CREACION" in acciones
        assert "MODIFICACION" in acciones
        assert "CAMBIO_ESTADO" in acciones
        assert "MOVIMIENTO" in acciones
        assert "ELIMINACION" in acciones

    def test_cp0242_cada_accion_es_entrada_separada(self, client):
        """CP-0242 (HP) — CA-4: Cada acción aparece como entrada independiente en la auditoría."""
        tid = _crear_envio(client)
        client.patch(f"/envios/{tid}/contacto", json=CONTACTO_NUEVO)

        entradas = _get_auditoria(client, tid).json()
        assert len(entradas) == 2  # CREACION + MODIFICACION

    def test_cp0242_historial_ordenado_cronologicamente(self, client):
        """CP-0242 (HP) — CA-4: Las entradas de auditoría están ordenadas cronológicamente."""
        tid = _crear_envio(client)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION,
        })
        entradas = _get_auditoria(client, tid).json()
        fechas = [e["fecha_hora"] for e in entradas]
        assert fechas == sorted(fechas)


# ── CP-0243 — CA-5: envío sin acciones adicionales ───────────────────────────

class TestCP0243SoloCreacion:

    def test_cp0243_envio_recien_creado_tiene_una_sola_entrada(self, client):
        """CP-0243 (HP) — CA-5: Envío recién creado → auditoría con exactamente 1 entrada."""
        tid = _crear_envio(client)
        entradas = _get_auditoria(client, tid).json()
        assert len(entradas) == 1

    def test_cp0243_la_unica_entrada_es_creacion(self, client):
        """CP-0243 (HP) — CA-5: La única entrada de un envío recién creado es de tipo CREACION."""
        tid = _crear_envio(client)
        entradas = _get_auditoria(client, tid).json()
        assert entradas[0]["accion"] == "CREACION"

    def test_cp0243_creacion_no_tiene_estado_inicial(self, client):
        """CP-0243 (HP) — CA-5: La entrada de CREACION tiene estado_inicial en None."""
        tid = _crear_envio(client)
        entradas = _get_auditoria(client, tid).json()
        assert entradas[0]["estado_inicial"] is None


# ── CP-0244 — CA-6: registros no modificables ────────────────────────────────

class TestCP0244RegistrosNoModificables:

    def test_cp0244_put_en_auditoria_retorna_405(self, client):
        """CP-0244 (HP) — CA-6: PUT sobre /auditoria devuelve 405 (método no permitido)."""
        tid = _crear_envio(client)
        assert client.put(f"/envios/{tid}/auditoria", json={}).status_code == 405

    def test_cp0244_patch_en_auditoria_retorna_405(self, client):
        """CP-0244 (HP) — CA-6: PATCH sobre /auditoria devuelve 405 (método no permitido)."""
        tid = _crear_envio(client)
        assert client.patch(f"/envios/{tid}/auditoria", json={}).status_code == 405

    def test_cp0244_delete_en_auditoria_retorna_405(self, client):
        """CP-0244 (HP) — CA-6: DELETE sobre /auditoria devuelve 405 (método no permitido)."""
        tid = _crear_envio(client)
        assert client.delete(f"/envios/{tid}/auditoria").status_code == 405


# ── CP-0245 — CA-7 HP: acceso al endpoint ────────────────────────────────────

class TestCP0245Acceso:

    def test_cp0245_endpoint_responde_200(self, client):
        """CP-0245 (HP) — CA-7: El endpoint /auditoria responde 200 (control de rol pendiente de JWT)."""
        tid = _crear_envio(client)
        assert _get_auditoria(client, tid).status_code == 200
