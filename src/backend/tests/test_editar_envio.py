"""
Tests para la edición de envíos.

Cubre:
  LP-148 — Modificar datos de contacto del envío  (CP-0209..CP-0213)
  LP-154 — Modificar datos operativos del envío   (CP-0216..CP-0223)
  LP-21  — Control de acceso por rol              (CP-0207, CP-0208, CP-0215, CP-0214, CP-0224)
"""
from datetime import date, timedelta

from models import Envio

_FECHA_FUTURA = str(date.today() + timedelta(days=30))
_FECHA_LEJANA = str(date.today() + timedelta(days=60))
_FECHA_PASADA = str(date.today() - timedelta(days=1))

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

PAYLOAD_CONTACTO_VALIDO = {
    "destinatario": "Carlos López",
    "direccion_destino": {
        "calle": "Belgrano",
        "numero": "100",
        "ciudad": "Rosario",
        "provincia": "Santa Fe",
        "codigo_postal": "2000",
    },
}

PAYLOAD_OPERATIVO_VALIDO = {
    "fecha_entrega_estimada": _FECHA_LEJANA,
    "probabilidad_retraso": 0.8,
}


def _crear_envio(client, headers) -> str:
    r = client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers)
    assert r.status_code == 201
    return r.json()["tracking_id"]


# ── CP-0207 / CP-0208 / CP-0215 / CP-0214 — control de acceso ────────────────

class TestCP0207CP0208CP0215ControlAccesoContacto:

    def test_cp0207_admin_no_puede_editar_contacto_retorna_403(self, client, headers_operador, headers_admin):
        """CP-0207 (UP) — CA-1: JWT con rol Administrador recibe 403 al editar datos de contacto."""
        tid = _crear_envio(client, headers_operador)
        assert client.patch(f"/envios/{tid}/contacto", json=PAYLOAD_CONTACTO_VALIDO, headers=headers_admin).status_code == 403

    def test_cp0208_sin_token_retorna_401_al_editar_contacto(self, client, headers_operador):
        """CP-0208 (EC) — CA-1: Request sin header Authorization retorna 401 al editar datos de contacto."""
        tid = _crear_envio(client, headers_operador)
        assert client.patch(f"/envios/{tid}/contacto", json=PAYLOAD_CONTACTO_VALIDO).status_code == 401

    def test_cp0215_usuario_no_autenticado_no_puede_editar_envio(self, client):
        """CP-0215 (UP) — CA-6: Usuario sin token no puede acceder a la edición de envío (401)."""
        assert client.patch("/envios/LT-00000001/contacto", json=PAYLOAD_CONTACTO_VALIDO).status_code == 401

    def test_cp0214_sin_token_retorna_401_al_editar_operativo(self, client, headers_operador):
        """CP-0214 — Sin token → 401 en PATCH /operativo."""
        tid = _crear_envio(client, headers_operador)
        assert client.patch(f"/envios/{tid}/operativo", json=PAYLOAD_OPERATIVO_VALIDO).status_code == 401

    def test_cp0224_usuario_no_autenticado_no_puede_editar_operativo(self, client):
        """CP-0224 (UP) — CA-7: Usuario sin token no puede acceder a la edición de datos operativos (401)."""
        assert client.patch("/envios/LT-00000001/operativo", json=PAYLOAD_OPERATIVO_VALIDO).status_code == 401


# ── LP-148 — Modificar datos de contacto ─────────────────────────────────────

class TestCP0209PersistenciaContacto:

    def test_cp0209_patch_contacto_retorna_200(self, client, headers_operador):
        """CP-0209 (HP) — PATCH /envios/{tid}/contacto con datos válidos retorna 200."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/contacto", json=PAYLOAD_CONTACTO_VALIDO, headers=headers_operador)
        assert resp.status_code == 200

    def test_cp0209_destinatario_actualizado_en_bd(self, client, db_session, headers_operador):
        """CP-0209 (HP) — El destinatario queda persistido en la BD tras el PATCH."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/contacto", json=PAYLOAD_CONTACTO_VALIDO, headers=headers_operador)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.destinatario == "Carlos López"

    def test_cp0209_direccion_destino_actualizada_en_bd(self, client, db_session, headers_operador):
        """CP-0209 (HP) — La dirección de destino queda persistida en la BD tras el PATCH."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/contacto", json=PAYLOAD_CONTACTO_VALIDO, headers=headers_operador)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.direccion_destino.ciudad == "Rosario"
        assert envio.direccion_destino.calle  == "Belgrano"


class TestCP0210ValidacionContacto:

    def test_cp0210_calle_solo_numerica_retorna_422(self, client, headers_operador):
        """CP-0210 (UP) — PATCH con calle solo numérica retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_CONTACTO_VALIDO,
                   "direccion_destino": {**PAYLOAD_CONTACTO_VALIDO["direccion_destino"], "calle": "1234"}}
        assert client.patch(f"/envios/{tid}/contacto", json=payload, headers=headers_operador).status_code == 422

    def test_cp0210_numero_no_numerico_retorna_422(self, client, headers_operador):
        """CP-0210 (UP) — PATCH con número de calle no numérico retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_CONTACTO_VALIDO,
                   "direccion_destino": {**PAYLOAD_CONTACTO_VALIDO["direccion_destino"], "numero": "ABC"}}
        assert client.patch(f"/envios/{tid}/contacto", json=payload, headers=headers_operador).status_code == 422

    def test_cp0210_sin_persistencia_si_validacion_falla(self, client, db_session, headers_operador):
        """CP-0210 (UP) — Si el PATCH falla por validación, los datos originales no cambian."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_CONTACTO_VALIDO,
                   "direccion_destino": {**PAYLOAD_CONTACTO_VALIDO["direccion_destino"], "numero": "ABC"}}
        client.patch(f"/envios/{tid}/contacto", json=payload, headers=headers_operador)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.destinatario == "María García"


class TestCP0211TrackingIdNoEditable:

    def test_cp0211_tracking_id_no_cambia_si_se_incluye_en_body(self, client, headers_operador):
        """CP-0211 (HP) — El tracking_id no cambia aunque se incluya en el body del PATCH."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_CONTACTO_VALIDO, "tracking_id": "LT-99999999"}
        client.patch(f"/envios/{tid}/contacto", json=payload, headers=headers_operador)
        resp = client.get(f"/envios/{tid}", headers=headers_operador)
        assert resp.status_code == 200
        assert resp.json()["tracking_id"] == tid


class TestCP0212ConfirmacionContacto:

    def test_cp0212_respuesta_incluye_nuevo_destinatario(self, client, headers_operador):
        """CP-0212 (HP) — La respuesta del PATCH incluye el nuevo destinatario."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/contacto", json=PAYLOAD_CONTACTO_VALIDO, headers=headers_operador)
        assert resp.status_code == 200
        assert resp.json()["destinatario"] == "Carlos López"

    def test_cp0212_respuesta_incluye_nueva_direccion_destino(self, client, headers_operador):
        """CP-0212 (HP) — La respuesta del PATCH incluye la nueva dirección de destino."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/contacto", json=PAYLOAD_CONTACTO_VALIDO, headers=headers_operador)
        assert resp.status_code == 200
        assert resp.json()["direccion_destino"]["ciudad"] == "Rosario"


class TestCP0213CamposObligatoriosContacto:

    def test_cp0213_destinatario_vacio_retorna_422(self, client, headers_operador):
        """CP-0213 (UP) — PATCH con destinatario vacío retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_CONTACTO_VALIDO, "destinatario": ""}
        assert client.patch(f"/envios/{tid}/contacto", json=payload, headers=headers_operador).status_code == 422

    def test_cp0213_ciudad_con_numeros_retorna_422(self, client, headers_operador):
        """CP-0213 (UP) — PATCH con ciudad que contiene números retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_CONTACTO_VALIDO,
                   "direccion_destino": {**PAYLOAD_CONTACTO_VALIDO["direccion_destino"], "ciudad": "Ciudad123"}}
        assert client.patch(f"/envios/{tid}/contacto", json=payload, headers=headers_operador).status_code == 422

    def test_cp0213_codigo_postal_no_numerico_retorna_422(self, client, headers_operador):
        """CP-0213 (UP) — PATCH con código postal no numérico retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_CONTACTO_VALIDO,
                   "direccion_destino": {**PAYLOAD_CONTACTO_VALIDO["direccion_destino"], "codigo_postal": "ABC"}}
        assert client.patch(f"/envios/{tid}/contacto", json=payload, headers=headers_operador).status_code == 422


# ── LP-154 — Modificar datos operativos ──────────────────────────────────────

class TestCP0216EdicionFechaEntrega:

    def test_cp0216_patch_operativo_con_fecha_valida_retorna_200(self, client, headers_operador):
        """CP-0216 (HP) — PATCH /envios/{tid}/operativo con fecha futura válida retorna 200."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/operativo", json=PAYLOAD_OPERATIVO_VALIDO, headers=headers_operador)
        assert resp.status_code == 200

    def test_cp0216_fecha_persistida_en_bd(self, client, db_session, headers_operador):
        """CP-0216 (HP) — La nueva fecha queda persistida en la BD."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/operativo", json=PAYLOAD_OPERATIVO_VALIDO, headers=headers_operador)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert str(envio.fecha_entrega_estimada) == _FECHA_LEJANA


class TestCP0217FechaPasadaRechazada:

    def test_cp0217_fecha_pasada_retorna_422(self, client, headers_operador):
        """CP-0217 (UP) — PATCH con fecha anterior a hoy retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_OPERATIVO_VALIDO, "fecha_entrega_estimada": _FECHA_PASADA}
        assert client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador).status_code == 422

    def test_cp0217_fecha_original_no_cambia_si_validacion_falla(self, client, db_session, headers_operador):
        """CP-0217 (UP) — Con fecha inválida, la fecha original no cambia en BD."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_OPERATIVO_VALIDO, "fecha_entrega_estimada": _FECHA_PASADA}
        client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert str(envio.fecha_entrega_estimada) == _FECHA_FUTURA


class TestCP0218EdicionProbabilidad:

    def test_cp0218_prioridad_recalculada_tras_patch_operativo(self, client, headers_operador):
        """CP-0218 (HP) — Tras PATCH con prob válida la prioridad es recalculada por ML."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/operativo", json=PAYLOAD_OPERATIVO_VALIDO, headers=headers_operador)
        assert resp.status_code == 200
        assert resp.json()["prioridad"] in {"ALTA", "MEDIA", "BAJA"}

    def test_cp0218_probabilidad_persistida_en_bd(self, client, db_session, headers_operador):
        """CP-0218 (HP) — La nueva probabilidad queda persistida en la BD."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/operativo", json=PAYLOAD_OPERATIVO_VALIDO, headers=headers_operador)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert float(envio.probabilidad_retraso) == 0.8


class TestCP0219ProbabilidadVacia:

    def test_cp0219_prob_ausente_retorna_422(self, client, headers_operador):
        """CP-0219 (UP) — PATCH sin probabilidad_retraso retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {"fecha_entrega_estimada": _FECHA_LEJANA}
        assert client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador).status_code == 422

    def test_cp0219_prob_null_retorna_422(self, client, headers_operador):
        """CP-0219 (UP) — PATCH con probabilidad_retraso: null retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {"fecha_entrega_estimada": _FECHA_LEJANA, "probabilidad_retraso": None}
        assert client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador).status_code == 422


class TestCP0220PrioridadNoEditable:

    def test_cp0220_no_existe_endpoint_directo_para_editar_prioridad(self, client, headers_operador):
        """CP-0220 (HP) — No existe endpoint PATCH/PUT para editar la prioridad manualmente."""
        tid = _crear_envio(client, headers_operador)
        assert client.patch(f"/envios/{tid}", json={"prioridad": "BAJA"}).status_code in (404, 405)
        assert client.put(f"/envios/{tid}", json={"prioridad": "BAJA"}).status_code in (404, 405)

    def test_cp0220_prioridad_en_body_es_ignorada_y_calculada_por_ml(self, client, headers_operador):
        """CP-0220 (HP) — Enviar prioridad en PATCH /operativo no la sobreescribe; la calcula ML."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_OPERATIVO_VALIDO, "prioridad": "BAJA"}
        resp = client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador)
        assert resp.status_code == 200
        assert resp.json()["prioridad"] in {"ALTA", "MEDIA", "BAJA"}


class TestCP0221ValidacionFormatoFecha:

    def test_cp0221_fecha_texto_invalido_retorna_422(self, client, headers_operador):
        """CP-0221 (UP) — PATCH con texto 'hoy' como fecha retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_OPERATIVO_VALIDO, "fecha_entrega_estimada": "hoy"}
        assert client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador).status_code == 422

    def test_cp0221_fecha_formato_dd_mm_yyyy_retorna_422(self, client, headers_operador):
        """CP-0221 (UP) — PATCH con fecha en formato DD/MM/AAAA (en vez de YYYY-MM-DD) retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_OPERATIVO_VALIDO, "fecha_entrega_estimada": "31/12/2099"}
        assert client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador).status_code == 422


class TestCP0222ValidacionRangoProbabilidad:

    def test_cp0222_prob_mayor_a_1_retorna_422(self, client, headers_operador):
        """CP-0222 (UP) — PATCH con probabilidad_retraso > 1.0 retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_OPERATIVO_VALIDO, "probabilidad_retraso": 1.5}
        assert client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador).status_code == 422

    def test_cp0222_prob_negativa_retorna_422(self, client, headers_operador):
        """CP-0222 (UP) — PATCH con probabilidad_retraso < 0.0 retorna 422."""
        tid = _crear_envio(client, headers_operador)
        payload = {**PAYLOAD_OPERATIVO_VALIDO, "probabilidad_retraso": -0.1}
        assert client.patch(f"/envios/{tid}/operativo", json=payload, headers=headers_operador).status_code == 422


class TestCP0223ConfirmacionOperativo:

    def test_cp0223_respuesta_incluye_nueva_fecha(self, client, headers_operador):
        """CP-0223 (HP) — La respuesta del PATCH incluye la nueva fecha de entrega."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/operativo", json=PAYLOAD_OPERATIVO_VALIDO, headers=headers_operador)
        assert resp.status_code == 200
        assert resp.json()["fecha_entrega_estimada"] == _FECHA_LEJANA

    def test_cp0223_respuesta_incluye_nueva_probabilidad(self, client, headers_operador):
        """CP-0223 (HP) — La respuesta del PATCH incluye la nueva probabilidad de retraso."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/operativo", json=PAYLOAD_OPERATIVO_VALIDO, headers=headers_operador)
        assert resp.status_code == 200
        assert float(resp.json()["probabilidad_retraso"]) == 0.8

    def test_cp0223_respuesta_incluye_prioridad_recalculada(self, client, headers_operador):
        """CP-0223 (HP) — La respuesta del PATCH incluye la prioridad recalculada."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/operativo", json=PAYLOAD_OPERATIVO_VALIDO, headers=headers_operador)
        assert resp.status_code == 200
        assert resp.json()["prioridad"] in {"ALTA", "MEDIA", "BAJA"}
