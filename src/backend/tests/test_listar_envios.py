"""
Tests para el listado de envíos.

Cubre:
  LP-9  — Consultar todos los envíos (CP-0023..0027)
  LP-21 — Control de acceso al listado (CP-0020, CP-0021, CP-0022)
"""
import time
from datetime import date, timedelta

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


# ── LP-21 — Control de acceso ─────────────────────────────────────────────────

def test_cp0022_sin_token_retorna_401(client):
    """CP-0022 — Request sin header Authorization debe recibir 401."""
    assert client.get("/envios/").status_code == 401


# ── LP-9 — Listado de envíos ──────────────────────────────────────────────────

def test_cp0023_listado_incluye_columnas_requeridas(client, headers_operador):
    """CP-0023 — Happy Path: el listado incluye tracking_id, remitente, destinatario, estado y created_at."""
    client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    resp = client.get("/envios/", headers=headers_operador)
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    for campo in ("tracking_id", "remitente", "destinatario", "estado", "created_at"):
        assert campo in item, f"Campo '{campo}' ausente en el item del listado"


def test_cp0024_busqueda_tracking_inexistente_retorna_vacio(client, headers_operador):
    """CP-0024 — Unhappy Path: búsqueda con tracking ID inexistente retorna lista vacía."""
    client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    resp = client.get("/envios/?q=LT-99999999", headers=headers_operador)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_cp0025_listado_sin_envios_retorna_total_cero(client, headers_operador):
    """CP-0025 — Happy Path: base de datos vacía → total=0 y lista vacía."""
    resp = client.get("/envios/", headers=headers_operador)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_cp0026_paginacion_funciona_correctamente(client, headers_operador):
    """CP-0026 — Happy Path: skip y limit permiten paginar el listado."""
    for _ in range(3):
        client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)

    r1 = client.get("/envios/?skip=0&limit=2", headers=headers_operador)
    r2 = client.get("/envios/?skip=2&limit=2", headers=headers_operador)

    assert r1.status_code == r2.status_code == 200
    assert len(r1.json()["items"]) == 2
    assert len(r2.json()["items"]) == 1
    assert r1.json()["total"] == r2.json()["total"] == 3


def test_cp0027_listado_responde_en_menos_de_3_segundos(client, headers_operador):
    """CP-0027 — NFR: GET /envios/ debe responder en menos de 3 segundos."""
    inicio = time.monotonic()
    resp = client.get("/envios/", headers=headers_operador)
    duracion = time.monotonic() - inicio
    assert resp.status_code == 200
    assert duracion < 3.0, f"Tiempo de respuesta: {duracion:.2f}s (límite: 3s)"
