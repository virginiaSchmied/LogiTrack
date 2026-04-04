"""
Tests para el registro de movimientos físicos de un envío.

Cubre:
  LP-253 — Crear movimiento de envío

  CP-0292 (HP)  — CA-1: Registro exitoso de un movimiento (core sin JWT)
  CP-0296 (UP)  — CA-3: Validación del campo de ubicación obligatorio
  CP-0297 (HP)  — CA-4: Múltiples movimientos sobre un mismo envío
  CP-0293 (UP)  — CA-1: JWT rol = Administrador → 403
  CP-0294 (EC)  — CA-1: Sin Authorization → 401
  CP-0299 (HP)  — CA-6: Sin token → 401
  CP-0300 (UP)  — CA-6: Sin token → 401 y redirige a login

Tests NO implementados:
  CP-0292 completo — CA-1: JWT rol = Operador → acceso permitido

Tests ya cubiertos en test_historial_envio.py:
  CP-0295 — CA-2: Movimiento visible en historial (TestCP0234MovimientosFisicos)
  CP-0298 — CA-5: Movimiento no cambia estado (test_cp0234_movimiento_no_cambia_estado_del_envio)
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

UBICACION_1 = {
    "calle": "Mitre", "numero": "200",
    "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000",
}

UBICACION_2 = {
    "calle": "Belgrano", "numero": "500",
    "ciudad": "Mendoza", "provincia": "Mendoza", "codigo_postal": "5500",
}


def _crear_envio(client, headers) -> str:
    r = client.post("/envios/", json=PAYLOAD_ENVIO, headers=headers)
    assert r.status_code == 201
    return r.json()["tracking_id"]


def _registrar_movimiento(client, tid: str, ubicacion: dict, headers=None):
    return client.post(f"/envios/{tid}/movimientos", json={"ubicacion": ubicacion}, headers=headers)


# ── CP-0292 — CA-1: registro exitoso ─────────────────────────────────────────

class TestCP0292RegistroExitoso:

    def test_cp0292_post_movimiento_retorna_201(self, client, headers_operador):
        """CP-0292 (HP) — CA-1: POST /movimientos con ubicación válida devuelve 201."""
        tid = _crear_envio(client, headers_operador)
        r = _registrar_movimiento(client, tid, UBICACION_1, headers_operador)
        assert r.status_code == 201

    def test_cp0292_respuesta_incluye_mensaje_de_confirmacion(self, client, headers_operador):
        """CP-0292 (HP) — CA-1: La respuesta incluye un mensaje de confirmación."""
        tid = _crear_envio(client, headers_operador)
        r = _registrar_movimiento(client, tid, UBICACION_1, headers_operador)
        assert "mensaje" in r.json()

    def test_cp0292_movimiento_queda_en_historial_del_envio(self, client, headers_operador):
        """CP-0292 (HP) — CA-1: El movimiento persiste como EventoDeEnvio de tipo MOVIMIENTO."""
        tid = _crear_envio(client, headers_operador)
        _registrar_movimiento(client, tid, UBICACION_1, headers_operador)

        historial = client.get(f"/envios/{tid}/historial", headers=headers_operador).json()
        tipos = [e["accion"] for e in historial]
        assert "MOVIMIENTO" in tipos


# ── CP-0296 — CA-3: ubicación obligatoria ────────────────────────────────────

class TestCP0296ValidacionUbicacion:

    def test_cp0296_sin_ubicacion_retorna_422(self, client, headers_operador):
        """CP-0296 (UP) — CA-3: POST /movimientos sin campo ubicación devuelve 422."""
        tid = _crear_envio(client, headers_operador)
        r = client.post(f"/envios/{tid}/movimientos", json={}, headers=headers_operador)
        assert r.status_code == 422

    def test_cp0296_ubicacion_nula_retorna_422(self, client, headers_operador):
        """CP-0296 (UP) — CA-3: POST /movimientos con ubicación null devuelve 422."""
        tid = _crear_envio(client, headers_operador)
        r = client.post(f"/envios/{tid}/movimientos", json={"ubicacion": None}, headers=headers_operador)
        assert r.status_code == 422

    def test_cp0296_envio_inexistente_retorna_404(self, client, headers_operador):
        """CP-0296 (EC) — CA-3: POST /movimientos sobre tracking_id inexistente devuelve 404."""
        r = _registrar_movimiento(client, "LT-99999999", UBICACION_1, headers_operador)
        assert r.status_code == 404


# ── CP-0297 — CA-4: múltiples movimientos ────────────────────────────────────

class TestCP0297MultiplesMovimientos:

    def test_cp0297_segundo_movimiento_se_agrega_al_historial(self, client, headers_operador):
        """CP-0297 (HP) — CA-4: Un segundo movimiento se agrega al historial sin reemplazar el anterior."""
        tid = _crear_envio(client, headers_operador)
        _registrar_movimiento(client, tid, UBICACION_1, headers_operador)
        _registrar_movimiento(client, tid, UBICACION_2, headers_operador)

        historial = client.get(f"/envios/{tid}/historial", headers=headers_operador).json()
        movimientos = [e for e in historial if e["accion"] == "MOVIMIENTO"]
        assert len(movimientos) == 2

    def test_cp0297_primer_movimiento_no_se_modifica(self, client, headers_operador):
        """CP-0297 (HP) — CA-4: El primer movimiento mantiene su ubicación original tras agregar un segundo."""
        tid = _crear_envio(client, headers_operador)
        _registrar_movimiento(client, tid, UBICACION_1, headers_operador)
        _registrar_movimiento(client, tid, UBICACION_2, headers_operador)

        historial = client.get(f"/envios/{tid}/historial", headers=headers_operador).json()
        movimientos = [e for e in historial if e["accion"] == "MOVIMIENTO"]
        assert movimientos[0]["ubicacion"]["ciudad"] == UBICACION_1["ciudad"]
        assert movimientos[1]["ubicacion"]["ciudad"] == UBICACION_2["ciudad"]


# ── CP-0293 / CP-0294 / CP-0299 / CP-0300 — control de acceso ────────────────

class TestCP0293CP0294CP0299CP0300ControlAccesoMovimiento:

    def test_cp0293_admin_no_puede_registrar_movimiento_retorna_403(self, client, headers_operador, headers_admin):
        """CP-0293 (UP) — CA-1: JWT con rol Administrador recibe 403 al registrar un movimiento."""
        tid = _crear_envio(client, headers_operador)
        resp = client.post(f"/envios/{tid}/movimientos", json={"nueva_ubicacion": UBICACION_1}, headers=headers_admin)
        assert resp.status_code == 403

    def test_cp0294_sin_token_retorna_401_al_registrar_movimiento(self, client, headers_operador):
        """CP-0294 (EC) — CA-1: Request sin header Authorization retorna 401 al registrar movimiento."""
        tid = _crear_envio(client, headers_operador)
        resp = client.post(f"/envios/{tid}/movimientos", json={"nueva_ubicacion": UBICACION_1})
        assert resp.status_code == 401

    def test_cp0299_sin_token_retorna_401(self, client, headers_operador):
        """CP-0299 (HP) — CA-6: POST /movimientos sin token retorna 401."""
        tid = _crear_envio(client, headers_operador)
        resp = _registrar_movimiento(client, tid, UBICACION_1)  # sin headers → 401
        assert resp.status_code == 401

    def test_cp0300_usuario_no_autenticado_no_puede_registrar_movimiento(self, client):
        """CP-0300 (UP) — CA-6: Usuario sin token no puede acceder al registro de movimientos (401)."""
        resp = client.post("/envios/LT-00000001/movimientos", json={"nueva_ubicacion": UBICACION_1})
        assert resp.status_code == 401
