"""
Tests para el cambio de estado de envíos.

Cubre:
  LP-11 — Cambiar estado de envío - flujo normal
    CP-0030  CA-2  Transición válida hacia adelante con ubicación       (Happy Path)
    CP-0031  CA-2  Transición válida con ubicación vacía                (Unhappy Path)
    CP-0032  CA-2  Transición válida con ubicación solo espacios        (Edge Case)
    CP-0033  CA-4  No se permite retroceder un estado                   (Unhappy Path)
    CP-0036  CA-5  Envío ELIMINADO no puede cambiar estado              (Edge Case)
    CP-0037  CA-6  Registro de auditoría por cada cambio de estado      (Happy Path)

Tests NO implementados (requieren autenticación JWT, no disponible en este prototipo):
  CP-0028  CA-1  — requiere frontend / JWT
  CP-0035  CA-5  — requiere JWT con rol = Supervisor
  CP-0038  CA-7  — requiere JWT con rol = Administrador → 403
  CP-0039  CA-7  — requiere request sin Authorization → 401
"""
from datetime import date, timedelta

from models import Envio, EventoDeEnvio, AccionEnvioEnum, EstadoEnvioEnum

_FECHA_FUTURA = str(date.today() + timedelta(days=30))

PAYLOAD_ENVIO = {
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

UBICACION_VALIDA = {
    "calle": "Mitre",
    "numero": "200",
    "ciudad": "Rosario",
    "provincia": "Santa Fe",
    "codigo_postal": "2000",
}


def _crear_envio(client) -> str:
    r = client.post("/envios/", json=PAYLOAD_ENVIO)
    assert r.status_code == 201
    return r.json()["tracking_id"]


def _avanzar_estado(client, tid: str, ubicacion: dict = None) -> dict:
    """Avanza el estado del envío al siguiente en el flujo normal."""
    ubicacion = ubicacion or UBICACION_VALIDA
    payload = {
        "nuevo_estado": _siguiente_estado(client, tid),
        "reusar_ubicacion_anterior": False,
        "nueva_ubicacion": ubicacion,
    }
    return client.patch(f"/envios/{tid}/estado", json=payload)


def _siguiente_estado(client, tid: str) -> str:
    flujo = ["REGISTRADO", "EN_TRANSITO", "EN_SUCURSAL", "EN_DISTRIBUCION", "ENTREGADO"]
    estado = client.get(f"/envios/{tid}").json()["estado"]
    return flujo[flujo.index(estado) + 1]


# ── CP-0030 — Transición válida hacia adelante con ubicación ─────────────────

class TestCP0030TransicionValida:

    def test_cp0030_retorna_200(self, client):
        """CP-0030 (HP) — PATCH /estado con estado válido y ubicación completa retorna 200."""
        tid = _crear_envio(client)
        resp = _avanzar_estado(client, tid)
        assert resp.status_code == 200

    def test_cp0030_estado_actualizado_en_bd(self, client, db_session):
        """CP-0030 (HP) — El estado queda actualizado en la BD tras la transición."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_TRANSITO

    def test_cp0030_respuesta_contiene_nuevo_estado(self, client):
        """CP-0030 (HP) — La respuesta refleja el nuevo estado del envío."""
        tid = _crear_envio(client)
        data = _avanzar_estado(client, tid).json()
        assert data["estado"] == "EN_TRANSITO"

    def test_cp0030_flujo_completo_hasta_entregado(self, client, db_session):
        """CP-0030 (HP) — Se puede avanzar por todos los estados hasta ENTREGADO."""
        tid = _crear_envio(client)
        for estado_esperado in ["EN_TRANSITO", "EN_SUCURSAL", "EN_DISTRIBUCION", "ENTREGADO"]:
            resp = _avanzar_estado(client, tid)
            assert resp.status_code == 200
            assert resp.json()["estado"] == estado_esperado


# ── CP-0031 — Campos de ubicación vacíos ─────────────────────────────────────

class TestCP0031UbicacionVacia:

    def _payload_con_ubicacion(self, tid, client, override: dict) -> dict:
        return {
            "nuevo_estado": _siguiente_estado(client, tid),
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, **override},
        }

    def test_cp0031_calle_vacia_retorna_422(self, client):
        """CP-0031 (UP) — Calle vacía en ubicación retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado",
                            json=self._payload_con_ubicacion(tid, client, {"calle": ""}))
        assert resp.status_code == 422

    def test_cp0031_ciudad_vacia_retorna_422(self, client):
        """CP-0031 (UP) — Ciudad vacía en ubicación retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado",
                            json=self._payload_con_ubicacion(tid, client, {"ciudad": ""}))
        assert resp.status_code == 422

    def test_cp0031_numero_vacio_retorna_422(self, client):
        """CP-0031 (UP) — Número vacío en ubicación retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado",
                            json=self._payload_con_ubicacion(tid, client, {"numero": ""}))
        assert resp.status_code == 422

    def test_cp0031_estado_no_cambia_si_validacion_falla(self, client, db_session):
        """CP-0031 (UP) — Si la validación falla, el estado del envío no se modifica."""
        tid = _crear_envio(client)
        client.patch(f"/envios/{tid}/estado",
                     json=self._payload_con_ubicacion(tid, client, {"calle": ""}))
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.REGISTRADO


# ── CP-0032 — Campos de ubicación con solo espacios ──────────────────────────

class TestCP0032UbicacionSoloEspacios:

    def _payload_con_ubicacion(self, tid, client, override: dict) -> dict:
        return {
            "nuevo_estado": _siguiente_estado(client, tid),
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, **override},
        }

    def test_cp0032_calle_espacios_retorna_422(self, client):
        """CP-0032 (EC) — Calle con solo espacios es tratada como vacía y retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado",
                            json=self._payload_con_ubicacion(tid, client, {"calle": "   "}))
        assert resp.status_code == 422

    def test_cp0032_ciudad_espacios_retorna_422(self, client):
        """CP-0032 (EC) — Ciudad con solo espacios es tratada como vacía y retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado",
                            json=self._payload_con_ubicacion(tid, client, {"ciudad": "   "}))
        assert resp.status_code == 422

    def test_cp0032_numero_espacios_retorna_422(self, client):
        """CP-0032 (EC) — Número con solo espacios es tratado como vacío y retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado",
                            json=self._payload_con_ubicacion(tid, client, {"numero": "   "}))
        assert resp.status_code == 422


# ── CP-0033 — No se permite retroceder un estado ─────────────────────────────

class TestCP0033NoRetroceder:

    def test_cp0033_retroceder_un_paso_retorna_422(self, client):
        """CP-0033 (UP) — Intentar retroceder un estado retorna 422."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)  # REGISTRADO → EN_TRANSITO
        payload = {
            "nuevo_estado": "REGISTRADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }
        resp = client.patch(f"/envios/{tid}/estado", json=payload)
        assert resp.status_code == 422

    def test_cp0033_mismo_estado_retorna_422(self, client):
        """CP-0033 (UP) — Intentar quedarse en el mismo estado retorna 422."""
        tid = _crear_envio(client)
        payload = {
            "nuevo_estado": "REGISTRADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }
        resp = client.patch(f"/envios/{tid}/estado", json=payload)
        assert resp.status_code == 422

    def test_cp0033_saltar_estado_retorna_422(self, client):
        """CP-0033 (UP) — Intentar saltar más de un estado adelante retorna 422."""
        tid = _crear_envio(client)
        payload = {
            "nuevo_estado": "EN_SUCURSAL",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }
        resp = client.patch(f"/envios/{tid}/estado", json=payload)
        assert resp.status_code == 422

    def test_cp0033_estado_no_cambia_al_intentar_retroceder(self, client, db_session):
        """CP-0033 (UP) — El estado en BD no cambia al intentar retroceder."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)  # REGISTRADO → EN_TRANSITO
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "REGISTRADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_TRANSITO


# ── CP-0036 — Envío ELIMINADO no puede cambiar estado ────────────────────────

class TestCP0036EnvioEliminado:

    def test_cp0036_cambio_estado_en_envio_eliminado_retorna_409(self, client):
        """CP-0036 (EC) — PATCH /estado sobre un envío ELIMINADO retorna 409."""
        tid = _crear_envio(client)
        client.delete(f"/envios/{tid}")
        payload = {
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }
        resp = client.patch(f"/envios/{tid}/estado", json=payload)
        assert resp.status_code == 409

    def test_cp0036_estado_permanece_eliminado(self, client, db_session):
        """CP-0036 (EC) — Tras el intento fallido, el estado sigue siendo ELIMINADO."""
        tid = _crear_envio(client)
        client.delete(f"/envios/{tid}")
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.ELIMINADO


# ── CP-0037 — Registro de auditoría por cambio de estado ─────────────────────

class TestCP0037Auditoria:

    def test_cp0037_se_crea_evento_cambio_estado(self, client, db_session):
        """CP-0037 (HP) — Un cambio de estado exitoso crea un EventoDeEnvio de CAMBIO_ESTADO."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                  .first())
        assert evento is not None

    def test_cp0037_evento_registra_estado_inicial_y_final(self, client, db_session):
        """CP-0037 (HP) — El EventoDeEnvio registra correctamente el estado anterior y el nuevo."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                  .first())
        assert evento.estado_inicial == EstadoEnvioEnum.REGISTRADO
        assert evento.estado_final   == EstadoEnvioEnum.EN_TRANSITO

    def test_cp0037_evento_registra_ubicacion(self, client, db_session):
        """CP-0037 (HP) — El EventoDeEnvio tiene una ubicacion_actual_id no nula."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                  .first())
        assert evento.ubicacion_actual_id is not None

    def test_cp0037_evento_registra_fecha_hora(self, client, db_session):
        """CP-0037 (HP) — El EventoDeEnvio tiene fecha_hora registrada."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                  .first())
        assert evento.fecha_hora is not None

    def test_cp0037_multiples_cambios_generan_multiples_eventos(self, client, db_session):
        """CP-0037 (HP) — Cada transición genera su propio evento de auditoría."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)  # → EN_TRANSITO
        _avanzar_estado(client, tid)  # → EN_SUCURSAL
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        eventos = (db_session.query(EventoDeEnvio)
                   .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                           EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                   .all())
        assert len(eventos) == 2
