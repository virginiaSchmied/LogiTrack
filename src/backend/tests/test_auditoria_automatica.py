"""
Tests para el registro automático de EventoDeEnvio por acción sobre envíos.

Cubre:
  LP-106 — Registrar automáticamente acciones sobre envíos

  CP-0103 (HP)  — CA-2: EventoDeEnvio generado al crear un envío
  CP-0104 (HP)  — CA-3: EventoDeEnvio generado al modificar un envío
  CP-0105 (UP)  — CA-3: Operación fallida (tracking inexistente) no genera EventoDeEnvio
  CP-0106 (EC)  — CA-3: Modificación de envío ELIMINADO → 409, sin EventoDeEnvio extra
  CP-0107 (HP)  — CA-4: EventoDeEnvio generado al cambiar estado
  CP-0108 (HP)  — CA-5: EventoDeEnvio generado al eliminar lógicamente
  CP-0109 (HP)  — CA-6: El registro se genera sin intervención del usuario
  CP-0111 (HP)  — CA-7: EventoDeEnvio generado al registrar movimiento físico
  CP-0112 (UP)  — CA-7: Movimiento con ubicación inválida no genera EventoDeEnvio
"""
from datetime import date, timedelta
from uuid import UUID

from models import EventoDeEnvio, AccionEnvioEnum, EstadoEnvioEnum

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


def _crear_envio(client, headers) -> tuple[str, str]:
    """Retorna (tracking_id, uuid) del envío creado."""
    r = client.post("/envios/", json=PAYLOAD_ENVIO, headers=headers)
    assert r.status_code == 201
    data = r.json()
    return data["tracking_id"], data["uuid"]


def _eventos_de(db_session, envio_uuid: str) -> list:
    return (
        db_session.query(EventoDeEnvio)
        .filter(EventoDeEnvio.envio_uuid == UUID(envio_uuid))
        .order_by(EventoDeEnvio.fecha_hora.asc())
        .all()
    )


def _avanzar_hasta_cancelado(client, tid: str, headers_op, headers_sup):
    client.patch(f"/envios/{tid}/estado", json={
        "nuevo_estado": "EN_DEPOSITO",
        "reusar_ubicacion_anterior": False,
        "nueva_ubicacion": UBICACION,
    }, headers=headers_op)
    client.patch(f"/envios/{tid}/estado", json={"nuevo_estado": "CANCELADO"}, headers=headers_sup)


# ── CP-0103 — CA-2: EventoDeEnvio al crear ───────────────────────────────────

class TestCP0103CreacionAutomatica:

    def test_cp0103_se_genera_un_evento_al_crear_envio(self, client, db_session, headers_supervisor):
        """CP-0103 (HP) — CA-2: Al crear un envío se genera exactamente 1 EventoDeEnvio."""
        _, uuid = _crear_envio(client, headers_supervisor)
        eventos = _eventos_de(db_session, uuid)
        assert len(eventos) == 1

    def test_cp0103_evento_tiene_accion_creacion(self, client, db_session, headers_supervisor):
        """CP-0103 (HP) — CA-2: El evento generado tiene accion = CREACION."""
        _, uuid = _crear_envio(client, headers_supervisor)
        evento = _eventos_de(db_session, uuid)[0]
        assert evento.accion == AccionEnvioEnum.CREACION

    def test_cp0103_evento_estado_inicial_es_null(self, client, db_session, headers_supervisor):
        """CP-0103 (HP) — CA-2: El EventoDeEnvio de creación tiene estado_inicial = None."""
        _, uuid = _crear_envio(client, headers_supervisor)
        evento = _eventos_de(db_session, uuid)[0]
        assert evento.estado_inicial is None

    def test_cp0103_evento_estado_final_es_registrado(self, client, db_session, headers_supervisor):
        """CP-0103 (HP) — CA-2: El EventoDeEnvio de creación tiene estado_final = REGISTRADO."""
        _, uuid = _crear_envio(client, headers_supervisor)
        evento = _eventos_de(db_session, uuid)[0]
        assert evento.estado_final == EstadoEnvioEnum.REGISTRADO

    def test_cp0103_evento_tiene_usuario_fecha_y_envio(self, client, db_session, headers_supervisor):
        """CP-0103 (HP) — CA-2: El EventoDeEnvio tiene usuario_uuid, fecha_hora y envio_uuid."""
        _, uuid = _crear_envio(client, headers_supervisor)
        evento = _eventos_de(db_session, uuid)[0]
        assert evento.usuario_uuid is not None
        assert evento.fecha_hora is not None
        assert str(evento.envio_uuid) == uuid


# ── CP-0104 — CA-3: EventoDeEnvio al modificar ───────────────────────────────

class TestCP0104ModificacionAutomatica:

    def test_cp0104_patch_contacto_genera_evento_modificacion(self, client, db_session, headers_supervisor):
        """CP-0104 (HP) — CA-3: PATCH /contacto genera EventoDeEnvio con accion = MODIFICACION."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.patch(f"/envios/{tid}/contacto", json=CONTACTO_NUEVO, headers=headers_supervisor)
        eventos = _eventos_de(db_session, uuid)
        acciones = [e.accion for e in eventos]
        assert AccionEnvioEnum.MODIFICACION in acciones

    def test_cp0104_patch_operativo_genera_evento_modificacion(self, client, db_session, headers_supervisor):
        """CP-0104 (HP) — CA-3: PATCH /operativo genera EventoDeEnvio con accion = MODIFICACION."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.patch(f"/envios/{tid}/operativo", json={
            "fecha_entrega_estimada": _FECHA_FUTURA,
            "probabilidad_retraso": 0.8,
        }, headers=headers_supervisor)
        eventos = _eventos_de(db_session, uuid)
        acciones = [e.accion for e in eventos]
        assert AccionEnvioEnum.MODIFICACION in acciones

    def test_cp0104_estado_inicial_y_final_son_estado_actual(self, client, db_session, headers_supervisor):
        """CP-0104 (HP) — CA-3: En MODIFICACION, estado_inicial == estado_final == estado actual."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.patch(f"/envios/{tid}/contacto", json=CONTACTO_NUEVO, headers=headers_supervisor)
        evento_mod = next(
            e for e in _eventos_de(db_session, uuid)
            if e.accion == AccionEnvioEnum.MODIFICACION
        )
        assert evento_mod.estado_inicial == EstadoEnvioEnum.REGISTRADO
        assert evento_mod.estado_final == EstadoEnvioEnum.REGISTRADO


# ── CP-0105 — CA-3 UP: operación fallida no genera EventoDeEnvio ─────────────

class TestCP0105ModificacionFallida:

    def test_cp0105_tracking_inexistente_retorna_404(self, client, headers_supervisor):
        """CP-0105 (UP) — CA-3: PATCH sobre tracking inexistente devuelve 404."""
        r = client.patch("/envios/LT-99999999/contacto", json=CONTACTO_NUEVO, headers=headers_supervisor)
        assert r.status_code == 404

    def test_cp0105_operacion_fallida_no_genera_evento(self, client, db_session, headers_supervisor):
        """CP-0105 (UP) — CA-3: Una modificación rechazada no persiste ningún EventoDeEnvio."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        eventos_antes = len(_eventos_de(db_session, uuid))
        # Intentar modificar con tracking_id incorrecto (falla, no afecta al envío creado)
        client.patch("/envios/LT-99999999/contacto", json=CONTACTO_NUEVO, headers=headers_supervisor)
        assert len(_eventos_de(db_session, uuid)) == eventos_antes


# ── CP-0106 — CA-3 EC: modificar envío ELIMINADO ─────────────────────────────

class TestCP0106ModificacionEliminado:

    def test_cp0106_modificar_eliminado_retorna_409(self, client, headers_operador, headers_supervisor):
        """CP-0106 (EC) — CA-3: PATCH sobre envío ELIMINADO devuelve 409."""
        tid, _ = _crear_envio(client, headers_supervisor)
        _avanzar_hasta_cancelado(client, tid, headers_operador, headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        r = client.patch(f"/envios/{tid}/contacto", json=CONTACTO_NUEVO, headers=headers_supervisor)
        assert r.status_code == 409

    def test_cp0106_modificar_eliminado_no_genera_nuevo_evento(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0106 (EC) — CA-3: El rechazo de modificación sobre ELIMINADO no crea EventoDeEnvio extra."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        _avanzar_hasta_cancelado(client, tid, headers_operador, headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        eventos_antes = len(_eventos_de(db_session, uuid))
        client.patch(f"/envios/{tid}/contacto", json=CONTACTO_NUEVO, headers=headers_supervisor)
        assert len(_eventos_de(db_session, uuid)) == eventos_antes


# ── CP-0107 — CA-4: EventoDeEnvio al cambiar estado ──────────────────────────

class TestCP0107CambioEstadoAutomatico:

    def test_cp0107_cambio_estado_genera_evento(self, client, db_session, headers_supervisor):
        """CP-0107 (HP) — CA-4: PATCH /estado genera EventoDeEnvio con accion = CAMBIO_ESTADO."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION,
        }, headers=headers_supervisor)
        acciones = [e.accion for e in _eventos_de(db_session, uuid)]
        assert AccionEnvioEnum.CAMBIO_ESTADO in acciones

    def test_cp0107_evento_registra_estado_inicial_y_final_correctos(self, client, db_session, headers_supervisor):
        """CP-0107 (HP) — CA-4: El EventoDeEnvio registra estado_inicial y estado_final correctos."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION,
        }, headers=headers_supervisor)
        evento = next(
            e for e in _eventos_de(db_session, uuid)
            if e.accion == AccionEnvioEnum.CAMBIO_ESTADO
        )
        assert evento.estado_inicial == EstadoEnvioEnum.REGISTRADO
        assert evento.estado_final == EstadoEnvioEnum.EN_DEPOSITO

    def test_cp0107_evento_registra_ubicacion(self, client, db_session, headers_supervisor):
        """CP-0107 (HP) — CA-4: El EventoDeEnvio de CAMBIO_ESTADO incluye ubicacion_actual_id."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION,
        }, headers=headers_supervisor)
        evento = next(
            e for e in _eventos_de(db_session, uuid)
            if e.accion == AccionEnvioEnum.CAMBIO_ESTADO
        )
        assert evento.ubicacion_actual_id is not None


# ── CP-0108 — CA-5: EventoDeEnvio al eliminar ────────────────────────────────

class TestCP0108EliminacionAutomatica:

    def test_cp0108_eliminacion_genera_evento(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0108 (HP) — CA-5: DELETE genera EventoDeEnvio con accion = ELIMINACION."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        _avanzar_hasta_cancelado(client, tid, headers_operador, headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        acciones = [e.accion for e in _eventos_de(db_session, uuid)]
        assert AccionEnvioEnum.ELIMINACION in acciones

    def test_cp0108_evento_estado_inicial_es_cancelado(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0108 (HP) — CA-5: El EventoDeEnvio de eliminación tiene estado_inicial = CANCELADO."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        _avanzar_hasta_cancelado(client, tid, headers_operador, headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        evento = next(
            e for e in _eventos_de(db_session, uuid)
            if e.accion == AccionEnvioEnum.ELIMINACION
        )
        assert evento.estado_inicial == EstadoEnvioEnum.CANCELADO

    def test_cp0108_evento_estado_final_es_eliminado(self, client, db_session, headers_operador, headers_supervisor):
        """CP-0108 (HP) — CA-5: El EventoDeEnvio de eliminación tiene estado_final = ELIMINADO."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        _avanzar_hasta_cancelado(client, tid, headers_operador, headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        evento = next(
            e for e in _eventos_de(db_session, uuid)
            if e.accion == AccionEnvioEnum.ELIMINACION
        )
        assert evento.estado_final == EstadoEnvioEnum.ELIMINADO


# ── CP-0109 — CA-6: registro sin intervención del usuario ────────────────────

class TestCP0109SinIntervencion:

    def test_cp0109_evento_creado_sin_campo_extra_en_request(self, client, db_session, headers_supervisor):
        """CP-0109 (HP) — CA-6: El EventoDeEnvio existe sin que el request incluya datos de auditoría."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        # El payload de creación no incluye ningún campo de auditoría
        assert "accion" not in PAYLOAD_ENVIO
        assert "usuario" not in PAYLOAD_ENVIO
        # Aun así el evento existe
        eventos = _eventos_de(db_session, uuid)
        assert len(eventos) == 1
        assert eventos[0].accion == AccionEnvioEnum.CREACION

    def test_cp0109_multiples_acciones_generan_eventos_automaticamente(self, client, db_session, headers_supervisor):
        """CP-0109 (HP) — CA-6: Cada operación genera su evento sin acción adicional del usuario."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.patch(f"/envios/{tid}/contacto", json=CONTACTO_NUEVO, headers=headers_supervisor)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION,
        }, headers=headers_supervisor)
        eventos = _eventos_de(db_session, uuid)
        acciones = {e.accion for e in eventos}
        assert AccionEnvioEnum.CREACION in acciones
        assert AccionEnvioEnum.MODIFICACION in acciones
        assert AccionEnvioEnum.CAMBIO_ESTADO in acciones


# ── CP-0111 — CA-7: EventoDeEnvio al registrar movimiento ────────────────────

class TestCP0111MovimientoAutomatico:

    def test_cp0111_movimiento_genera_evento(self, client, db_session, headers_supervisor):
        """CP-0111 (HP) — CA-7: POST /movimientos genera EventoDeEnvio con accion = MOVIMIENTO."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})
        acciones = [e.accion for e in _eventos_de(db_session, uuid)]
        assert AccionEnvioEnum.MOVIMIENTO in acciones

    def test_cp0111_evento_estado_inicial_igual_final(self, client, db_session, headers_supervisor):
        """CP-0111 (HP) — CA-7: En MOVIMIENTO, estado_inicial == estado_final == estado actual."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})
        evento = next(
            e for e in _eventos_de(db_session, uuid)
            if e.accion == AccionEnvioEnum.MOVIMIENTO
        )
        assert evento.estado_inicial == EstadoEnvioEnum.REGISTRADO
        assert evento.estado_final == EstadoEnvioEnum.REGISTRADO

    def test_cp0111_evento_registra_ubicacion_nueva(self, client, db_session, headers_supervisor):
        """CP-0111 (HP) — CA-7: El EventoDeEnvio de MOVIMIENTO incluye ubicacion_actual_id."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        client.post(f"/envios/{tid}/movimientos", json={"ubicacion": UBICACION})
        evento = next(
            e for e in _eventos_de(db_session, uuid)
            if e.accion == AccionEnvioEnum.MOVIMIENTO
        )
        assert evento.ubicacion_actual_id is not None


# ── CP-0112 — CA-7 UP: movimiento inválido no genera EventoDeEnvio ───────────

class TestCP0112MovimientoInvalido:

    def test_cp0112_ubicacion_faltante_retorna_422(self, client, headers_supervisor):
        """CP-0112 (UP) — CA-7: POST /movimientos sin ubicación devuelve 422."""
        tid, _ = _crear_envio(client, headers_supervisor)
        r = client.post(f"/envios/{tid}/movimientos", json={})
        assert r.status_code == 422

    def test_cp0112_ubicacion_invalida_no_genera_evento(self, client, db_session, headers_supervisor):
        """CP-0112 (UP) — CA-7: Movimiento rechazado no persiste ningún EventoDeEnvio extra."""
        tid, uuid = _crear_envio(client, headers_supervisor)
        eventos_antes = len(_eventos_de(db_session, uuid))
        client.post(f"/envios/{tid}/movimientos", json={})
        assert len(_eventos_de(db_session, uuid)) == eventos_antes
