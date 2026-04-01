"""
Tests para la creación de envíos.

Cubre:
  LP-2   — Registrar datos básicos del envío (CP-0003..0009)
  LP-104 — Generar tracking ID automático    (CP-0094..0097)
  LP-131 — Validar campos obligatorios       (CP-0174..0185, CP-0175)

Tests NO implementados (requieren autenticación JWT, no disponible en este prototipo):
  CP-0001 — JWT rol=Operador requerido para acceder al formulario
  CP-0002 — JWT rol=Administrador debe recibir 401
"""
import pytest
from datetime import date, timedelta

# ── Payload base ──────────────────────────────────────────────────────────────

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


# ── LP-2 / LP-131 — Campos obligatorios y validaciones ───────────────────────

def test_cp0003_crear_envio_datos_validos(client):
    """CP-0003 / CP-0006 / CP-0176 / CP-0179 / CP-0181 — Happy Path: POST con todos los campos válidos retorna 201."""
    response = client.post("/envios/", json=PAYLOAD_VALIDO)
    assert response.status_code == 201


def test_cp0004_remitente_vacio_retorna_422(client):
    """CP-0004 / CP-0177 / CP-0180 / CP-0182 — Unhappy Path: remitente vacío → 422."""
    payload = {**PAYLOAD_VALIDO, "remitente": ""}
    assert client.post("/envios/", json=payload).status_code == 422


def test_cp0005_remitente_solo_espacios_retorna_422(client):
    """CP-0005 — Edge Case: remitente con solo espacios debe ser rechazado con 422."""
    payload = {**PAYLOAD_VALIDO, "remitente": "   "}
    assert client.post("/envios/", json=payload).status_code == 422


def test_cp0007_numero_domicilio_con_letras_retorna_422(client):
    """CP-0007 — Unhappy Path: número de domicilio no numérico → 422."""
    payload = {
        **PAYLOAD_VALIDO,
        "direccion_origen": {**PAYLOAD_VALIDO["direccion_origen"], "numero": "Abc"},
    }
    assert client.post("/envios/", json=payload).status_code == 422


def test_cp0008_envio_creado_aparece_en_listado(client):
    """CP-0008 — Happy Path: el envío registrado exitosamente aparece en el listado."""
    client.post("/envios/", json=PAYLOAD_VALIDO)
    resp = client.get("/envios/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_cp0009_envio_fallido_no_aparece_en_listado(client):
    """CP-0009 — Unhappy Path: un envío rechazado no aparece en el listado."""
    client.post("/envios/", json={**PAYLOAD_VALIDO, "remitente": ""})
    resp = client.get("/envios/")
    assert resp.json()["total"] == 0


def test_cp0174_error_422_incluye_detalle_del_campo(client):
    """CP-0174 — NFR: el error 422 incluye mensajes descriptivos con el campo afectado."""
    payload = {**PAYLOAD_VALIDO, "remitente": ""}
    resp = client.post("/envios/", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    assert any("remitente" in str(err.get("loc", "")) for err in body["detail"])


def test_cp0178_formato_invalido_y_campo_vacio_retorna_422(client):
    """CP-0178 — Unhappy Path: número no numérico + remitente vacío → 422."""
    payload = {
        **PAYLOAD_VALIDO,
        "remitente": "",
        "direccion_origen": {**PAYLOAD_VALIDO["direccion_origen"], "numero": "ABC"},
    }
    assert client.post("/envios/", json=payload).status_code == 422


def test_cp0183_campos_direccion_validos_retorna_201(client):
    """CP-0183 — Happy Path: campos de dirección con formato correcto → 201."""
    assert client.post("/envios/", json=PAYLOAD_VALIDO).status_code == 201


def test_cp0184_campo_direccion_vacio_retorna_422(client):
    """CP-0184 — Unhappy Path: calle de dirección de origen vacía → 422."""
    payload = {
        **PAYLOAD_VALIDO,
        "direccion_origen": {**PAYLOAD_VALIDO["direccion_origen"], "calle": ""},
    }
    assert client.post("/envios/", json=payload).status_code == 422


def test_cp0185_fecha_entrega_ausente_retorna_422(client):
    """CP-0185 — Unhappy Path: fecha_entrega_estimada ausente → 422."""
    payload = {k: v for k, v in PAYLOAD_VALIDO.items() if k != "fecha_entrega_estimada"}
    assert client.post("/envios/", json=payload).status_code == 422


# ── LP-104 — Generación automática de tracking ID ────────────────────────────

def test_cp0094_tracking_id_generado_automaticamente(client):
    """CP-0094 — Happy Path: el sistema genera tracking_id automático con formato LT-XXXXXXXX."""
    resp = client.post("/envios/", json=PAYLOAD_VALIDO)
    assert resp.status_code == 201
    assert resp.json()["tracking_id"].startswith("LT-")


def test_cp0095_tracking_ids_son_unicos(client):
    """CP-0095 — Happy Path: dos envíos consecutivos reciben tracking IDs distintos."""
    r1 = client.post("/envios/", json=PAYLOAD_VALIDO)
    r2 = client.post("/envios/", json=PAYLOAD_VALIDO)
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["tracking_id"] != r2.json()["tracking_id"]


def test_cp0096_tracking_id_visible_en_respuesta(client):
    """CP-0096 — Happy Path: la respuesta de creación incluye el tracking_id no vacío."""
    resp = client.post("/envios/", json=PAYLOAD_VALIDO)
    assert resp.status_code == 201
    assert resp.json().get("tracking_id", "") != ""


def test_cp0097_no_existe_endpoint_para_editar_tracking_id(client):
    """CP-0097 — Happy Path: PATCH y PUT sobre un envío retornan 404 o 405 (tracking_id no editable)."""
    r = client.post("/envios/", json=PAYLOAD_VALIDO)
    tid = r.json()["tracking_id"]
    assert client.patch(f"/envios/{tid}", json={"tracking_id": "LT-99"}).status_code in (404, 405)
    assert client.put(f"/envios/{tid}", json={"tracking_id": "LT-99"}).status_code in (404, 405)


# ── LP-118 — Persistencia de prioridad ───────────────────────────────────────

_PAYLOAD_CON_PROB = {
    **PAYLOAD_VALIDO,
    "probabilidad_retraso": 0.85,
}

_PRIORIDADES_VALIDAS = {"ALTA", "MEDIA", "BAJA"}


def test_cp0150_prioridad_persistida_al_crear_con_prob_retraso(client):
    """CP-0150 (HP) — CA-1: POST con probabilidad_retraso → prioridad asignada automáticamente en la respuesta."""
    resp = client.post("/envios/", json=_PAYLOAD_CON_PROB)
    assert resp.status_code == 201
    assert resp.json()["prioridad"] in _PRIORIDADES_VALIDAS


def test_cp0151_probabilidad_invalida_retorna_422_sin_crear_envio(client):
    """CP-0151 (UP) — CA-1: probabilidad_retraso fuera de rango → 422, envío no creado."""
    payload = {**PAYLOAD_VALIDO, "probabilidad_retraso": 1.5}
    resp = client.post("/envios/", json=payload)
    assert resp.status_code == 422
    assert client.get("/envios/").json()["total"] == 0


def test_cp0152_prioridad_en_respuesta_pertenece_a_valores_validos(client):
    """CP-0152 (HP) — CA-3: El valor de prioridad persistido siempre pertenece a {ALTA, MEDIA, BAJA}."""
    resp = client.post("/envios/", json=_PAYLOAD_CON_PROB)
    assert resp.status_code == 201
    assert resp.json()["prioridad"] in _PRIORIDADES_VALIDAS


def test_cp0153_prioridad_no_es_editable_manualmente(client):
    """CP-0153 (HP) — CA-4: No existe endpoint para editar la prioridad manualmente."""
    r = client.post("/envios/", json=_PAYLOAD_CON_PROB)
    tid = r.json()["tracking_id"]
    assert client.patch(f"/envios/{tid}", json={"prioridad": "BAJA"}).status_code in (404, 405)
    assert client.put(f"/envios/{tid}", json={"prioridad": "BAJA"}).status_code in (404, 405)


# ── LP-131 — Edge Case ────────────────────────────────────────────────────────

def test_cp0175_payload_vacio_devuelve_422_con_detalle(client):
    """CP-0175 — Edge Case: POST con payload vacío retorna 422 con detalle de los campos faltantes."""
    res = client.post("/envios/", json={})
    assert res.status_code == 422
    campos_error = [e["loc"][-1] for e in res.json()["detail"]]
    for campo in ("remitente", "destinatario", "probabilidad_retraso",
                  "fecha_entrega_estimada", "direccion_origen", "direccion_destino"):
        assert campo in campos_error
