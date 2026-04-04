"""
Tests para el historial de estados y movimientos de un envío.

Cubre:
  LP-160 — Consultar historial de estados de un envío

  CP-0225 (NFR)  — CA-1: El historial carga en menos de 3 segundos
  CP-0229 (HP)   — CA-3: Cada entrada tiene los campos correctos y no incluye usuario
  CP-0230 (HP)   — CA-4: Historial con un único estado (recién creado)
  CP-0231 (HP)   — CA-5: Historial incluye reversiones de excepción
  CP-0234 (HP)   — CA-6: Historial incluye movimientos físicos con ubicación

Tests NO implementados (requieren JWT y control de roles):
  CP-0226 — CA-2: JWT rol ∈ {Operador, Supervisor} → acceso permitido
  CP-0227 — CA-2: JWT rol = Administrador → 403
  CP-0228 — CA-2: Sin Authorization → 401
  CP-0232 — CA-5: JWT rol = Administrador → 403
  CP-0233 — CA-5: Sin Authorization → 401
  CP-0235 — CA-7: Usuario autenticado puede acceder
  CP-0236 — CA-7: Usuario no autenticado → 401 y redirige a login
"""
import time
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


def _crear_envio(client, headers) -> str:
    r = client.post("/envios/", json=PAYLOAD_ENVIO, headers=headers)
    assert r.status_code == 201
    return r.json()["tracking_id"]


def _cambiar_estado(client, tid: str, nuevo_estado: str, ubicacion: dict = None, headers=None):
    payload = {"nuevo_estado": nuevo_estado, "reusar_ubicacion_anterior": False}
    if ubicacion:
        payload["nueva_ubicacion"] = ubicacion
    r = client.patch(f"/envios/{tid}/estado", json=payload, headers=headers)
    assert r.status_code == 200
    return r


def _get_historial(client, tid: str):
    return client.get(f"/envios/{tid}/historial")


# ── CP-0225 — NFR: carga en menos de 3 segundos ──────────────────────────────

class TestCP0225CargaRapida:

    def test_cp0225_historial_responde_en_menos_de_3_segundos(self, client, headers_supervisor):
        """CP-0225 (NFR) — GET /historial responde en menos de 3 segundos."""
        tid = _crear_envio(client, headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)
        _cambiar_estado(client, tid, "EN_TRANSITO", UBICACION, headers=headers_supervisor)

        inicio = time.time()
        r = _get_historial(client, tid)
        elapsed = time.time() - inicio

        assert r.status_code == 200
        assert elapsed < 3.0, f"El historial tardó {elapsed:.2f}s (límite: 3s)"


# ── CP-0229 — CA-3: estructura de cada entrada ───────────────────────────────

class TestCP0229EstructuraEntradas:

    def test_cp0229_cada_entrada_tiene_accion_estado_fecha(self, client, headers_supervisor):
        """CP-0229 (HP) — CA-3: Cada entrada tiene accion, estado y fecha_hora."""
        tid = _crear_envio(client, headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)

        entradas = _get_historial(client, tid).json()
        for entrada in entradas:
            assert "accion" in entrada
            assert "estado" in entrada
            assert "fecha_hora" in entrada

    def test_cp0229_entradas_no_incluyen_usuario(self, client, headers_supervisor):
        """CP-0229 (HP) — CA-3: La respuesta no expone el usuario que realizó la acción."""
        tid = _crear_envio(client, headers_supervisor)
        entradas = _get_historial(client, tid).json()
        for entrada in entradas:
            assert "usuario" not in entrada
            assert "usuario_email" not in entrada
            assert "usuario_uuid" not in entrada

    def test_cp0229_movimiento_incluye_ubicacion(self, client, headers_supervisor):
        """CP-0229 (HP) — CA-3: Entradas de tipo MOVIMIENTO incluyen ubicacion."""
        tid = _crear_envio(client, headers_supervisor)
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})

        entradas = _get_historial(client, tid).json()
        movimiento = next(e for e in entradas if e["accion"] == "MOVIMIENTO")
        assert movimiento["ubicacion"] is not None
        assert movimiento["ubicacion"]["ciudad"] == UBICACION["ciudad"]


# ── CP-0230 — CA-4: historial con un único estado ────────────────────────────

class TestCP0230UnicoEstado:

    def test_cp0230_envio_recien_creado_tiene_una_entrada(self, client, headers_supervisor):
        """CP-0230 (HP) — CA-4: Envío recién creado → historial con 1 sola entrada."""
        tid = _crear_envio(client, headers_supervisor)
        entradas = _get_historial(client, tid).json()
        assert len(entradas) == 1

    def test_cp0230_unica_entrada_es_creacion_con_estado_registrado(self, client, headers_supervisor):
        """CP-0230 (HP) — CA-4: La única entrada es de tipo CREACION con estado REGISTRADO."""
        tid = _crear_envio(client, headers_supervisor)
        entradas = _get_historial(client, tid).json()
        assert entradas[0]["accion"] == "CREACION"
        assert entradas[0]["estado"] == "REGISTRADO"

    def test_cp0230_retorna_200_sin_errores(self, client, headers_supervisor):
        """CP-0230 (HP) — CA-4: El endpoint responde 200 para envío con único estado."""
        tid = _crear_envio(client, headers_supervisor)
        assert _get_historial(client, tid).status_code == 200


# ── CP-0231 — CA-5: reversiones de excepción ─────────────────────────────────

class TestCP0231ReversionExcepcion:

    def test_cp0231_reversion_aparece_como_entrada_separada(self, client, headers_supervisor):
        """CP-0231 (HP) — CA-5: La reversión de un estado de excepción aparece en el historial."""
        tid = _crear_envio(client, headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)
        _cambiar_estado(client, tid, "RETRASADO", UBICACION, headers=headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)  # reversión

        entradas = _get_historial(client, tid).json()
        estados = [e["estado"] for e in entradas]
        assert "RETRASADO" in estados
        assert estados.count("EN_DEPOSITO") == 2  # primera vez + reversión

    def test_cp0231_reversion_tiene_fecha_hora_propia(self, client, headers_supervisor):
        """CP-0231 (HP) — CA-5: La entrada de reversión tiene su propia fecha y hora."""
        tid = _crear_envio(client, headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)
        _cambiar_estado(client, tid, "RETRASADO", UBICACION, headers=headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)

        entradas = _get_historial(client, tid).json()
        for entrada in entradas:
            assert entrada["fecha_hora"] is not None

    def test_cp0231_orden_cronologico_incluye_reversion(self, client, headers_supervisor):
        """CP-0231 (HP) — CA-5: El historial con reversión está ordenado cronológicamente."""
        tid = _crear_envio(client, headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)
        _cambiar_estado(client, tid, "RETRASADO", UBICACION, headers=headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)

        entradas = _get_historial(client, tid).json()
        acciones = [e["accion"] for e in entradas]
        # CREACION → CAMBIO_ESTADO × 3 en orden
        assert acciones[0] == "CREACION"
        assert all(a == "CAMBIO_ESTADO" for a in acciones[1:])


# ── CP-0234 — CA-6: movimientos físicos en el historial ──────────────────────

class TestCP0234MovimientosFisicos:

    def test_cp0234_movimiento_aparece_en_historial(self, client, headers_supervisor):
        """CP-0234 (HP) — CA-6: Un MOVIMIENTO registrado aparece en el historial."""
        tid = _crear_envio(client, headers_supervisor)
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})

        entradas = _get_historial(client, tid).json()
        tipos = [e["accion"] for e in entradas]
        assert "MOVIMIENTO" in tipos

    def test_cp0234_movimiento_muestra_ubicacion_ciudad_provincia(self, client, headers_supervisor):
        """CP-0234 (HP) — CA-6: El movimiento en el historial muestra ciudad y provincia."""
        tid = _crear_envio(client, headers_supervisor)
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})

        entradas = _get_historial(client, tid).json()
        mov = next(e for e in entradas if e["accion"] == "MOVIMIENTO")
        assert mov["ubicacion"]["ciudad"] == UBICACION["ciudad"]
        assert mov["ubicacion"]["provincia"] == UBICACION["provincia"]

    def test_cp0234_movimiento_intercalado_cronologicamente(self, client, headers_supervisor):
        """CP-0234 (HP) — CA-6: El movimiento aparece intercalado entre los cambios de estado."""
        tid = _crear_envio(client, headers_supervisor)
        _cambiar_estado(client, tid, "EN_DEPOSITO", UBICACION, headers=headers_supervisor)
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})
        _cambiar_estado(client, tid, "EN_TRANSITO", UBICACION, headers=headers_supervisor)

        entradas = _get_historial(client, tid).json()
        tipos = [e["accion"] for e in entradas]
        # CREACION, CAMBIO_ESTADO, MOVIMIENTO, CAMBIO_ESTADO
        idx_mov = tipos.index("MOVIMIENTO")
        ultimo_cambio = len(tipos) - 1 - tipos[::-1].index("CAMBIO_ESTADO")
        assert idx_mov > tipos.index("CREACION")
        assert idx_mov < ultimo_cambio

    def test_cp0234_movimiento_no_cambia_estado_del_envio(self, client, headers_supervisor):
        """CP-0234 (HP) — CA-6: Registrar un movimiento no modifica el estado del envío."""
        tid = _crear_envio(client, headers_supervisor)
        estado_antes = client.get(f"/envios/{tid}", headers=headers_supervisor).json()["estado"]
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})
        estado_despues = client.get(f"/envios/{tid}", headers=headers_supervisor).json()["estado"]
        assert estado_antes == estado_despues
