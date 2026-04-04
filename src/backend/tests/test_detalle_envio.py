"""
Tests para consulta de envío por tracking ID y búsqueda por destinatario.

Cubre:
  LP-142 — Consultar envío por tracking ID        (CP-0195, CP-0197, CP-0198, CP-0199, CP-0200, CP-0204, CP-0205)
  LP-197 — Buscar envío por datos del destinatario (CP-0247, CP-0249, CP-0250, CP-0251, CP-0252, CP-0253, CP-0254)

Tests NO implementados (requieren JWT con roles específicos):
  CP-0196, CP-0201, CP-0202, CP-0203 — requieren JWT con roles
  CP-0248                            — requiere JWT con roles
"""
import time
from datetime import date, timedelta

from models import EstadoEnvioEnum


_FECHA_FUTURA = str(date.today() + timedelta(days=30))

PAYLOAD_VALIDO = {
    "remitente": "Juan Pérez",
    "destinatario": "María García",
    "probabilidad_retraso": 0.5,
    "fecha_entrega_estimada": _FECHA_FUTURA,
    "direccion_origen": {
        "calle": "Av. Corrientes",
        "numero": "1234",
        "ciudad": "Buenos Aires",
        "provincia": "Buenos Aires",
        "codigo_postal": "1043",
    },
    "direccion_destino": {
        "calle": "San Martín",
        "numero": "567",
        "ciudad": "Córdoba",
        "provincia": "Córdoba",
        "codigo_postal": "5000",
    },
}


# ── LP-142 — Consulta por tracking ID ────────────────────────────────────────

def test_cp0195_detalle_responde_en_menos_de_3_segundos(client, headers_operador):
    """CP-0195 — NFR: GET /envios/{tracking_id} debe responder en menos de 3 segundos."""
    r = client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    tracking_id = r.json()["tracking_id"]
    inicio = time.monotonic()
    resp = client.get(f"/envios/{tracking_id}", headers=headers_operador)
    duracion = time.monotonic() - inicio
    assert resp.status_code == 200
    assert duracion < 3.0, f"Tiempo de respuesta: {duracion:.2f}s (límite: 3s)"


def test_cp0197_admin_no_puede_consultar_envio_por_tracking_id(client, headers_admin):
    """CP-0197 (UP) — CA-2: JWT con rol Administrador recibe 403 al consultar GET /envios/{tracking_id}."""
    # admin tampoco puede crear, usamos un tracking_id ficticio
    resp = client.get("/envios/LT-00000001", headers=headers_admin)
    assert resp.status_code == 403


def test_cp0198_sin_token_retorna_401_al_consultar_envio(client, headers_operador):
    """CP-0198 (EC) — CA-2: Request sin header Authorization retorna 401 al consultar GET /envios/{tracking_id}."""
    r = client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    tracking_id = r.json()["tracking_id"]
    resp = client.get(f"/envios/{tracking_id}")
    assert resp.status_code == 401


def test_cp0199_tracking_id_inexistente_retorna_404_con_mensaje(client, headers_operador):
    """CP-0199 / CP-0204 — Tracking ID inexistente retorna 404 con mensaje descriptivo."""
    resp = client.get("/envios/LT-99999999", headers=headers_operador)
    assert resp.status_code == 404
    assert "detail" in resp.json()
    assert "LT-99999999" in resp.json()["detail"]


def test_cp0205_tracking_id_con_caracteres_especiales_retorna_404(client, headers_operador):
    """CP-0205 — Tracking ID con caracteres especiales retorna 404."""
    resp = client.get("/envios/!!INVALIDO!!", headers=headers_operador)
    assert resp.status_code == 404


# ── LP-197 — Búsqueda por destinatario ───────────────────────────────────────

def test_cp0247_busqueda_responde_en_menos_de_3_segundos(client, headers_operador):
    """CP-0247 — NFR: GET /envios/?q=término debe responder en menos de 3 segundos."""
    client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    inicio = time.monotonic()
    resp = client.get("/envios/?q=García", headers=headers_operador)
    duracion = time.monotonic() - inicio
    assert resp.status_code == 200
    assert duracion < 3.0, f"Tiempo de respuesta: {duracion:.2f}s (límite: 3s)"


def test_cp0249_admin_no_puede_buscar_por_destinatario(client, headers_admin):
    """CP-0249 (UP) — CA-2: JWT con rol Administrador recibe 403 al buscar GET /envios/?q=..."""
    resp = client.get("/envios/?q=García", headers=headers_admin)
    assert resp.status_code == 403


def test_cp0250_sin_token_retorna_401_al_buscar_por_destinatario(client):
    """CP-0250 (EC) — CA-2: Request sin header Authorization retorna 401 al buscar GET /envios/?q=..."""
    resp = client.get("/envios/?q=García")
    assert resp.status_code == 401


def test_cp0253_usuario_no_autenticado_no_puede_acceder_a_busqueda(client):
    """CP-0253 (HP) — CA-5: Usuario sin token no puede acceder a la búsqueda por destinatario (401)."""
    resp = client.get("/envios/")
    assert resp.status_code == 401


def test_cp0251_busqueda_destinatario_inexistente_retorna_vacio(client, headers_operador):
    """CP-0251 — Happy Path: búsqueda por destinatario sin coincidencias retorna lista vacía."""
    client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    resp = client.get("/envios/?q=DestinatarioQueNoExiste99999", headers=headers_operador)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_cp0252_cp0017_envios_eliminados_no_aparecen_en_listado(client, db_session, headers_operador):
    """CP-0252 — Happy Path: envíos con estado ELIMINADO no aparecen en el listado."""
    from models import Envio
    r = client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    tracking_id = r.json()["tracking_id"]

    envio = db_session.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    envio.estado = EstadoEnvioEnum.ELIMINADO
    db_session.commit()

    resp = client.get("/envios/", headers=headers_operador)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_cp0254_busqueda_vacia_retorna_todos_los_activos(client, headers_operador):
    """CP-0254 — Unhappy Path: q vacío retorna todos los envíos activos."""
    client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    resp = client.get("/envios/?q=", headers=headers_operador)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


# ── LP-118 — Prioridad visible en detalle ────────────────────────────────────

_PAYLOAD_CON_PROB = {**PAYLOAD_VALIDO, "probabilidad_retraso": 0.85}


def test_cp0154_prioridad_visible_en_detalle_del_envio(client, headers_operador):
    """CP-0154 (HP) — CA-5: La prioridad clasificada es visible en el detalle del envío."""
    r = client.post("/envios/", json=_PAYLOAD_CON_PROB, headers=headers_operador)
    tid = r.json()["tracking_id"]
    resp = client.get(f"/envios/{tid}", headers=headers_operador)
    assert resp.status_code == 200
    assert "prioridad" in resp.json()
    assert resp.json()["prioridad"] in {"ALTA", "MEDIA", "BAJA"}
