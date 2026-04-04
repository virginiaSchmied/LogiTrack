"""
Tests para la eliminación lógica de envíos.

Cubre:
  LP-7  — Eliminar envío
  LP-21 — Solo Supervisor puede eliminar (LP-249 CA-1, LP-252 CA-3)

  CP-0012 (UP) — CA-1: Operador no puede eliminar → 403
  CP-0013 (UP) — CA-1: Administrador no puede eliminar → 403
  CP-0014 (EC) — CA-1: Sin token → 401
  CP-0016 (HP) — CA-3: Eliminación lógica exitosa
  CP-0017 (HP) — CA-4: El envío eliminado desaparece del listado general
  CP-0018 (HP) — CA-5: El historial de auditoría se conserva
"""
from datetime import date, timedelta

from models import Envio, EventoDeEnvio, EstadoEnvioEnum, AccionEnvioEnum

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


def _crear_envio(client, headers_operador) -> str:
    """Crea un envío y devuelve su tracking_id."""
    r = client.post("/envios/", json=PAYLOAD_VALIDO, headers=headers_operador)
    assert r.status_code == 201
    return r.json()["tracking_id"]


# ── CP-0012 / CP-0013 / CP-0014 — CA-1: control de acceso ───────────────────

class TestCP0012CP0013CP0014ControlAccesoEliminacion:

    def test_cp0012_operador_no_puede_eliminar_retorna_403(self, client, headers_operador):
        """CP-0012 (UP) — CA-1: JWT con rol Operador recibe 403 al intentar eliminar un envío."""
        tid = _crear_envio(client, headers_operador)
        assert client.delete(f"/envios/{tid}", headers=headers_operador).status_code == 403

    def test_cp0013_admin_no_puede_eliminar_retorna_403(self, client, headers_operador, headers_admin):
        """CP-0013 (UP) — CA-1: JWT con rol Administrador recibe 403 al intentar eliminar un envío."""
        tid = _crear_envio(client, headers_operador)
        assert client.delete(f"/envios/{tid}", headers=headers_admin).status_code == 403

    def test_cp0014_sin_token_retorna_401(self, client, headers_operador):
        """CP-0014 (EC) — CA-1: Request sin header Authorization retorna 401 al intentar eliminar."""
        tid = _crear_envio(client, headers_operador)
        assert client.delete(f"/envios/{tid}").status_code == 401


# ── CP-0016 — CA-3: Eliminación lógica exitosa ────────────────────────────────

class TestCP0016EliminacionLogica:

    def test_cp0016_delete_retorna_200(self, client, headers_operador, headers_supervisor):
        """CP-0016 (HP) — DELETE sobre envío CANCELADO retorna 200."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        resp = client.delete(f"/envios/{tid}", headers=headers_supervisor)
        assert resp.status_code == 200

    def test_cp0016_envio_queda_marcado_como_eliminado_en_bd(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0016 (HP) — Después del DELETE, el estado en BD es ELIMINADO."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio is not None
        assert envio.estado == EstadoEnvioEnum.ELIMINADO

    def test_cp0016_envio_no_borrado_fisicamente(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0016 (HP) — El registro del envío sigue existiendo en BD tras la eliminación."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio is not None

    def test_cp0016_delete_envio_inexistente_retorna_404(self, client, headers_supervisor):
        """CP-0016 (UP) — DELETE sobre tracking ID inexistente retorna 404."""
        resp = client.delete("/envios/LT-99999999", headers=headers_supervisor)
        assert resp.status_code == 404

    def test_cp0016_delete_envio_ya_eliminado_retorna_409(self, client, headers_operador, headers_supervisor):
        """CP-0016 (Edge) — DELETE sobre envío ya eliminado retorna 409."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        resp = client.delete(f"/envios/{tid}", headers=headers_supervisor)
        assert resp.status_code == 409


# ── CP-0017 — CA-4: El envío eliminado desaparece del listado ─────────────────

class TestCP0017EliminadoNoAparece:

    def test_cp0017_envio_eliminado_no_aparece_en_listado(self, client, headers_operador, headers_supervisor):
        """CP-0017 (HP) — Envío eliminado no aparece en GET /envios/."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        resp = client.get("/envios/", headers=headers_operador)
        assert resp.status_code == 200
        tracking_ids = [e["tracking_id"] for e in resp.json()["items"]]
        assert tid not in tracking_ids

    def test_cp0017_total_disminuye_tras_eliminacion(self, client, headers_operador, headers_supervisor):
        """CP-0017 (HP) — El total del listado disminuye en 1 tras eliminar un envío."""
        _crear_envio(client, headers_operador)
        _crear_envio(client, headers_operador)
        total_antes = client.get("/envios/", headers=headers_operador).json()["total"]
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        total_despues = client.get("/envios/", headers=headers_operador).json()["total"]
        assert total_despues == total_antes

    def test_cp0017_envios_activos_no_se_ven_afectados(self, client, headers_operador, headers_supervisor):
        """CP-0017 (HP) — Los envíos activos siguen apareciendo tras eliminar otro."""
        tid_activo = _crear_envio(client, headers_operador)
        tid_a_eliminar = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid_a_eliminar}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid_a_eliminar}", headers=headers_supervisor)
        resp = client.get("/envios/", headers=headers_operador)
        tracking_ids = [e["tracking_id"] for e in resp.json()["items"]]
        assert tid_activo in tracking_ids


# ── CP-0018 — CA-5: El historial de auditoría se conserva ────────────────────

class TestCP0018HistorialConservado:

    def test_cp0018_evento_eliminacion_registrado_en_bd(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0018 (HP) — Tras el DELETE existe un EventoDeEnvio con accion=ELIMINACION."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = db_session.query(EventoDeEnvio).filter(
            EventoDeEnvio.envio_uuid == envio.uuid,
            EventoDeEnvio.accion == AccionEnvioEnum.ELIMINACION,
        ).first()
        assert evento is not None

    def test_cp0018_evento_eliminacion_refleja_estado_final_correcto(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0018 (HP) — El EventoDeEnvio de ELIMINACION tiene estado_final = ELIMINADO."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = db_session.query(EventoDeEnvio).filter(
            EventoDeEnvio.envio_uuid == envio.uuid,
            EventoDeEnvio.accion == AccionEnvioEnum.ELIMINACION,
        ).first()
        assert evento.estado_final == EstadoEnvioEnum.ELIMINADO

    def test_cp0018_evento_creacion_previo_se_conserva(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0018 (HP) — El EventoDeEnvio de CREACION sigue existiendo tras la eliminación."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento_creacion = db_session.query(EventoDeEnvio).filter(
            EventoDeEnvio.envio_uuid == envio.uuid,
            EventoDeEnvio.accion == AccionEnvioEnum.CREACION,
        ).first()
        assert evento_creacion is not None

    def test_cp0018_historial_tiene_dos_eventos_tras_eliminacion(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0018 (HP) — Tras cancelar y eliminar el historial tiene CREACION, CAMBIO_ESTADO y ELIMINACION."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        eventos = db_session.query(EventoDeEnvio).filter(
            EventoDeEnvio.envio_uuid == envio.uuid,
        ).all()
        assert len(eventos) == 3
        acciones = {e.accion for e in eventos}
        assert AccionEnvioEnum.CREACION    in acciones
        assert AccionEnvioEnum.CAMBIO_ESTADO in acciones
        assert AccionEnvioEnum.ELIMINACION in acciones
