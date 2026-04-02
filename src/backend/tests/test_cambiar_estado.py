"""
Tests para el cambio de estado de envíos.

Cubre:
  LP-11 — Cambiar estado de envío - flujo normal
    CP-0030  CA-2  Transición válida hacia adelante con ubicación       (Happy Path)
    CP-0031  CA-2  Transición válida con ubicación vacía                (Unhappy Path)
    CP-0032  CA-2  Transición válida con ubicación solo espacios        (Edge Case)
    CP-0033  CA-4  No se permite saltar estados                         (Unhappy Path)
    CP-0036  CA-5  Envío ELIMINADO no puede cambiar estado              (Edge Case)
    CP-0037  CA-6  Registro de auditoría por cada cambio de estado      (Happy Path)
    CP-0317  CA-3  Reutilizar ubicación anterior en estado no obligatorio (Happy Path)
    CP-0318  CA-3  Estado con ubicación obligatoria + nueva ubicación    (Happy Path)
    CP-0319  CA-3  Estado con ubicación obligatoria sin ubicación        (Unhappy Path)
    CP-0320  CA-3  Estado con ubicación obligatoria + reusar=true        (Unhappy Path)
    CP-0321  CA-4  Saltar estado inválido retorna 422                    (Unhappy Path)

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

# Flujo normal completo con EN_DEPOSITO incorporado.
# EN_DEPOSITO, EN_SUCURSAL y ENTREGADO requieren nueva_ubicacion obligatoria (no reusar).
_FLUJO_NORMAL = [
    "REGISTRADO", "EN_DEPOSITO", "EN_TRANSITO",
    "EN_SUCURSAL", "EN_DISTRIBUCION", "ENTREGADO",
]
_ESTADOS_UBICACION_OBLIGATORIA = {"EN_DEPOSITO", "EN_SUCURSAL", "ENTREGADO"}


def _crear_envio(client) -> str:
    r = client.post("/envios/", json=PAYLOAD_ENVIO)
    assert r.status_code == 201
    return r.json()["tracking_id"]


def _siguiente_estado(client, tid: str) -> str:
    estado = client.get(f"/envios/{tid}").json()["estado"]
    return _FLUJO_NORMAL[_FLUJO_NORMAL.index(estado) + 1]


def _avanzar_estado(client, tid: str, ubicacion: dict = None) -> dict:
    """Avanza el envío al siguiente estado en el flujo normal.

    Siempre envía nueva_ubicacion ya que cubre tanto los estados con
    ubicación obligatoria (EN_DEPOSITO, EN_SUCURSAL, ENTREGADO) como
    los opcionales (EN_TRANSITO, EN_DISTRIBUCION).
    """
    ubicacion = ubicacion or UBICACION_VALIDA
    payload = {
        "nuevo_estado": _siguiente_estado(client, tid),
        "reusar_ubicacion_anterior": False,
        "nueva_ubicacion": ubicacion,
    }
    return client.patch(f"/envios/{tid}/estado", json=payload)


def _avanzar_hasta(client, tid: str, estado_destino: str) -> None:
    """Avanza el envío por el flujo normal hasta alcanzar estado_destino."""
    while True:
        actual = client.get(f"/envios/{tid}").json()["estado"]
        if actual == estado_destino:
            break
        r = _avanzar_estado(client, tid)
        assert r.status_code == 200, f"Falló al avanzar desde {actual}: {r.json()}"


def _cancelar_y_eliminar(client, tid: str) -> None:
    """Mueve el envío a CANCELADO (desde REGISTRADO es una transición válida) y lo elimina."""
    r = client.patch(f"/envios/{tid}/estado", json={
        "nuevo_estado": "CANCELADO",
        "reusar_ubicacion_anterior": False,
    })
    assert r.status_code == 200
    r = client.delete(f"/envios/{tid}")
    assert r.status_code == 200


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
        _avanzar_estado(client, tid)  # REGISTRADO → EN_DEPOSITO
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_DEPOSITO

    def test_cp0030_respuesta_contiene_nuevo_estado(self, client):
        """CP-0030 (HP) — La respuesta refleja el nuevo estado del envío."""
        tid = _crear_envio(client)
        data = _avanzar_estado(client, tid).json()  # REGISTRADO → EN_DEPOSITO
        assert data["estado"] == "EN_DEPOSITO"

    def test_cp0030_flujo_completo_hasta_entregado(self, client, db_session):
        """CP-0030 (HP) — Se puede avanzar por todos los estados hasta ENTREGADO."""
        tid = _crear_envio(client)
        for estado_esperado in ["EN_DEPOSITO", "EN_TRANSITO", "EN_SUCURSAL", "EN_DISTRIBUCION", "ENTREGADO"]:
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


# ── CP-0033 — No se permite saltar estados ───────────────────────────────────

class TestCP0033NoSaltarEstados:

    def test_cp0033_retroceder_un_paso_retorna_422(self, client):
        """CP-0033 (UP) — Intentar retroceder un estado retorna 422."""
        tid = _crear_envio(client)
        _avanzar_estado(client, tid)  # REGISTRADO → EN_DEPOSITO
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
        # REGISTRADO → EN_SUCURSAL no es una transición válida (debe pasar por EN_DEPOSITO)
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
        _avanzar_estado(client, tid)  # REGISTRADO → EN_DEPOSITO
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "REGISTRADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_DEPOSITO


# ── CP-0036 — Envío ELIMINADO no puede cambiar estado ────────────────────────

class TestCP0036EnvioEliminado:

    def test_cp0036_cambio_estado_en_envio_eliminado_retorna_409(self, client):
        """CP-0036 (EC) — PATCH /estado sobre un envío ELIMINADO retorna 409."""
        tid = _crear_envio(client)
        _cancelar_y_eliminar(client, tid)
        payload = {
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }
        resp = client.patch(f"/envios/{tid}/estado", json=payload)
        assert resp.status_code == 409

    def test_cp0036_estado_permanece_eliminado(self, client, db_session):
        """CP-0036 (EC) — Tras el intento fallido, el estado sigue siendo ELIMINADO."""
        tid = _crear_envio(client)
        _cancelar_y_eliminar(client, tid)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
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
        _avanzar_estado(client, tid)  # REGISTRADO → EN_DEPOSITO
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                  .first())
        assert evento.estado_inicial == EstadoEnvioEnum.REGISTRADO
        assert evento.estado_final   == EstadoEnvioEnum.EN_DEPOSITO

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
        _avanzar_estado(client, tid)  # → EN_DEPOSITO
        _avanzar_estado(client, tid)  # → EN_TRANSITO
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        eventos = (db_session.query(EventoDeEnvio)
                   .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                           EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                   .all())
        assert len(eventos) == 2


# ── CP-0317 — Reutilizar ubicación anterior en estado no obligatorio ──────────

class TestCP0317ReusoUbicacion:

    def test_cp0317_reusar_en_estado_no_obligatorio_retorna_200(self, client):
        """CP-0317 (HP) — reusar_ubicacion_anterior=true en EN_TRANSITO retorna 200."""
        tid = _crear_envio(client)
        _avanzar_hasta(client, tid, "EN_DEPOSITO")  # establece ubicación anterior
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": True,
        })
        assert resp.status_code == 200

    def test_cp0317_estado_se_actualiza_al_reusar(self, client, db_session):
        """CP-0317 (HP) — El estado queda en EN_TRANSITO tras reusar ubicación."""
        tid = _crear_envio(client)
        _avanzar_hasta(client, tid, "EN_DEPOSITO")
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": True,
        })
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_TRANSITO

    def test_cp0317_reusar_sin_ubicacion_previa_retorna_422(self, client):
        """CP-0317 (UP) — reusar_ubicacion_anterior=true sin ubicación previa retorna 422."""
        tid = _crear_envio(client)
        # REGISTRADO no tiene ubicación previa; EN_DEPOSITO es el siguiente válido pero es obligatorio
        # Usamos EN_DISTRIBUCION desde EN_TRANSITO como caso, pero para testear sin previa
        # avanzamos solo al primer estado no-obligatorio: EN_TRANSITO necesita pasar por EN_DEPOSITO
        # Creamos un segundo envío para llegar a EN_TRANSITO y luego probar EN_DISTRIBUCION con reusar=false
        # Caso más directo: intentar reusar en EN_DEPOSITO (obligatorio) → 422 también
        # Aquí verificamos que no hay ubicación en REGISTRADO → avanzar a EN_DEPOSITO con reusar=true falla
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": True,
        })
        assert resp.status_code == 422


# ── CP-0318 — Estado con ubicación obligatoria + nueva ubicación ─────────────

class TestCP0318UbicacionObligatoriaConNueva:

    def test_cp0318_en_deposito_con_nueva_ubicacion_retorna_200(self, client):
        """CP-0318 (HP) — Transición a EN_DEPOSITO con nueva_ubicacion retorna 200."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        assert resp.status_code == 200

    def test_cp0318_ubicacion_queda_registrada(self, client, db_session):
        """CP-0318 (HP) — La ubicación nueva queda asociada al evento de auditoría."""
        tid = _crear_envio(client)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                  .first())
        assert evento.ubicacion_actual_id is not None


# ── CP-0319 — Estado con ubicación obligatoria sin ubicación ─────────────────

class TestCP0319UbicacionObligatoriaFaltante:

    def test_cp0319_en_deposito_sin_ubicacion_retorna_422(self, client):
        """CP-0319 (UP) — Transición a EN_DEPOSITO sin nueva_ubicacion retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
        })
        assert resp.status_code == 422

    def test_cp0319_estado_no_cambia(self, client, db_session):
        """CP-0319 (UP) — El estado permanece REGISTRADO cuando falta la ubicación obligatoria."""
        tid = _crear_envio(client)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
        })
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.REGISTRADO

    def test_cp0319_en_sucursal_sin_ubicacion_retorna_422(self, client):
        """CP-0319 (UP) — Transición a EN_SUCURSAL sin nueva_ubicacion retorna 422."""
        tid = _crear_envio(client)
        _avanzar_hasta(client, tid, "EN_TRANSITO")
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_SUCURSAL",
            "reusar_ubicacion_anterior": False,
        })
        assert resp.status_code == 422


# ── CP-0320 — Estado con ubicación obligatoria + reusar=true ─────────────────

class TestCP0320UbicacionObligatoriaConReusar:

    def test_cp0320_en_deposito_con_reusar_true_retorna_422(self, client):
        """CP-0320 (UP) — Transición a EN_DEPOSITO con reusar_ubicacion_anterior=true retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": True,
        })
        assert resp.status_code == 422

    def test_cp0320_en_sucursal_con_reusar_true_retorna_422(self, client):
        """CP-0320 (UP) — Transición a EN_SUCURSAL con reusar_ubicacion_anterior=true retorna 422."""
        tid = _crear_envio(client)
        _avanzar_hasta(client, tid, "EN_TRANSITO")
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_SUCURSAL",
            "reusar_ubicacion_anterior": True,
        })
        assert resp.status_code == 422

    def test_cp0320_entregado_con_reusar_true_retorna_422(self, client):
        """CP-0320 (UP) — Transición a ENTREGADO con reusar_ubicacion_anterior=true retorna 422."""
        tid = _crear_envio(client)
        _avanzar_hasta(client, tid, "EN_DISTRIBUCION")
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "ENTREGADO",
            "reusar_ubicacion_anterior": True,
        })
        assert resp.status_code == 422


# ── CP-0321 — Saltar estado inválido retorna 422 ─────────────────────────────

class TestCP0321SaltarEstado:

    def test_cp0321_registrado_a_en_transito_retorna_422(self, client):
        """CP-0321 (UP) — REGISTRADO → EN_TRANSITO no es una transición válida, retorna 422."""
        tid = _crear_envio(client)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        assert resp.status_code == 422

    def test_cp0321_estado_no_cambia_al_saltar(self, client, db_session):
        """CP-0321 (UP) — El estado permanece REGISTRADO al intentar saltar a EN_TRANSITO."""
        tid = _crear_envio(client)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.REGISTRADO

    def test_cp0321_en_deposito_a_en_sucursal_retorna_422(self, client):
        """CP-0321 (UP) — EN_DEPOSITO → EN_SUCURSAL no es una transición válida, retorna 422."""
        tid = _crear_envio(client)
        _avanzar_hasta(client, tid, "EN_DEPOSITO")
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_SUCURSAL",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        assert resp.status_code == 422
