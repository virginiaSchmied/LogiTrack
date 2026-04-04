"""
Tests LP-82: Cambiar estado de envío - excepción

Cubre:
  LP-82 — Cambiar estado de envío - excepción
    CP-0322  CA-2  Supervisor asigna RETRASADO con ubicación completa                 (Happy Path)
    CP-0064  CA-2  Asignación de excepción con ubicación vacía                        (Unhappy Path)
    CP-0065  CA-2  Asignación de excepción con ubicación con solo espacios            (Edge Case)
    CP-0067  CA-3  CANCELADO no requiere ubicación                                    (Happy Path)
    CP-0066  CA-4  CANCELADO es irreversible                                          (Happy Path)
    CP-0071  CA-6  Reversión de excepción con ubicación completa                      (Happy Path)
    CP-0072  CA-6  Reversión con ubicación vacía o ausente es rechazada               (Unhappy Path)
    CP-0068  CA-6  Reversión vuelve al estado previo específico (RETRASADO→EN_TRANSITO) (Happy Path)
    CP-0323  CA-6  Reversión vuelve al estado previo específico (BLOQUEADO→EN_SUCURSAL) (Happy Path)
    CP-0073  CA-7  Reutilizar ubicación anterior al revertir excepción                (Happy Path)
    CP-0074  CA-8  BLOQUEADO inválido desde EN_TRANSITO                               (Unhappy Path)
    CP-0324  CA-8  BLOQUEADO inválido desde EN_DISTRIBUCION                           (Unhappy Path)
    CP-0325  CA-8  BLOQUEADO válido desde EN_DEPOSITO                                 (Happy Path)
    CP-0326  CA-9  Registro de auditoría por cambio de excepción                      (Happy Path)
    CP-0327  CA-9  Fallo de validación no genera evento de auditoría                  (Unhappy Path)
    CP-0328  CA-10 DELETE en envío CANCELADO retorna 200                              (Happy Path)
    CP-0329  CA-10 DELETE en envío no CANCELADO retorna 422                           (Unhappy Path)
    CP-0062  CA-1  Administrador no puede asignar estado de excepción → 403            (Unhappy Path)
    CP-0063  CA-1  Sin token → 401 al asignar estado de excepción                      (Edge Case)
    CP-0070  CA-5  Sin token → 401 al revertir estado de excepción                     (Edge Case)

Tests NO implementados (requieren autenticación JWT):
  CP-0061  CA-1  — requiere JWT con rol = Supervisor
  CP-0069  CA-5  — requiere JWT con rol = Operador → 403 al revertir excepción
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

_FLUJO_NORMAL = [
    "REGISTRADO", "EN_DEPOSITO", "EN_TRANSITO",
    "EN_SUCURSAL", "EN_DISTRIBUCION", "ENTREGADO",
]


def _crear_envio(client, headers) -> str:
    r = client.post("/envios/", json=PAYLOAD_ENVIO, headers=headers)
    assert r.status_code == 201
    return r.json()["tracking_id"]


def _avanzar_hasta(client, tid: str, estado_destino: str, headers) -> None:
    """Avanza por el flujo normal hasta alcanzar estado_destino con nueva_ubicacion en cada paso."""
    while True:
        actual = client.get(f"/envios/{tid}", headers=headers).json()["estado"]
        if actual == estado_destino:
            break
        idx = _FLUJO_NORMAL.index(actual)
        siguiente = _FLUJO_NORMAL[idx + 1]
        r = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": siguiente,
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers)
        assert r.status_code == 200, f"Fallo al avanzar {actual} → {siguiente}: {r.json()}"


def _asignar_excepcion(client, tid: str, estado: str, headers, ubicacion: dict = None) -> dict:
    """Asigna un estado de excepción (RETRASADO o BLOQUEADO) con ubicación."""
    return client.patch(f"/envios/{tid}/estado", json={
        "nuevo_estado": estado,
        "reusar_ubicacion_anterior": False,
        "nueva_ubicacion": ubicacion or UBICACION_VALIDA,
    }, headers=headers)


# ── CP-0322 — Asignación de RETRASADO con ubicación completa ─────────────────

class TestCP0322AsignacionExcepcionHP:

    def test_cp0322_retrasado_con_ubicacion_retorna_200(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0322 (HP) — Supervisor asigna RETRASADO a envío en EN_TRANSITO con ubicación → 200."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        assert resp.status_code == 200

    def test_cp0322_estado_actualizado_en_bd(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0322 (HP) — El estado queda en RETRASADO en la BD tras la asignación."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.RETRASADO

    def test_cp0322_respuesta_contiene_nuevo_estado(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0322 (HP) — La respuesta refleja el estado RETRASADO."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        data = _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor).json()
        assert data["estado"] == "RETRASADO"


# ── CP-0064 — Asignación de excepción con ubicación vacía ────────────────────

class TestCP0064UbicacionVacia:

    def test_cp0064_calle_vacia_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0064 (UP) — Calle vacía al asignar excepción retorna 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, "calle": ""},
        }, headers=headers_supervisor)
        assert resp.status_code == 422

    def test_cp0064_ciudad_vacia_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0064 (UP) — Ciudad vacía al asignar excepción retorna 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, "ciudad": ""},
        }, headers=headers_supervisor)
        assert resp.status_code == 422

    def test_cp0064_estado_no_cambia_si_validacion_falla(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0064 (UP) — El estado permanece EN_TRANSITO si la validación falla."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, "calle": ""},
        }, headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_TRANSITO


# ── CP-0065 — Asignación de excepción con ubicación con solo espacios ─────────

class TestCP0065UbicacionSoloEspacios:

    def test_cp0065_calle_espacios_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0065 (EC) — Calle con solo espacios al asignar excepción retorna 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, "calle": "   "},
        }, headers=headers_supervisor)
        assert resp.status_code == 422

    def test_cp0065_ciudad_espacios_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0065 (EC) — Ciudad con solo espacios al asignar excepción retorna 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, "ciudad": "   "},
        }, headers=headers_supervisor)
        assert resp.status_code == 422


# ── CP-0067 — CANCELADO no requiere ubicación ─────────────────────────────────

class TestCP0067CanceladoSinUbicacion:

    def test_cp0067_cancelado_sin_ubicacion_retorna_200(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0067 (HP) — PATCH a CANCELADO sin nueva_ubicacion retorna 200."""
        tid = _crear_envio(client, headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "CANCELADO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        assert resp.status_code == 200

    def test_cp0067_estado_actualizado_en_bd(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0067 (HP) — El estado queda en CANCELADO en la BD."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "CANCELADO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.CANCELADO

    def test_cp0067_evento_no_tiene_ubicacion(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0067 (HP) — El EventoDeEnvio de CANCELADO no registra ubicación."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "CANCELADO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.estado_final == EstadoEnvioEnum.CANCELADO)
                  .first())
        assert evento is not None
        assert evento.ubicacion_actual_id is None


# ── CP-0066 — CANCELADO es irreversible ───────────────────────────────────────

class TestCP0066CanceladoIrreversible:

    def test_cp0066_patch_desde_cancelado_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0066 (HP) — PATCH a cualquier estado desde CANCELADO retorna 422."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "CANCELADO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_supervisor)
        assert resp.status_code == 422

    def test_cp0066_estado_permanece_cancelado(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0066 (HP) — El estado permanece CANCELADO tras el intento fallido."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "CANCELADO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.CANCELADO


# ── CP-0071 — Reversión de excepción con ubicación completa ──────────────────

class TestCP0071ReversionHP:

    def test_cp0071_reversion_retrasado_retorna_200(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0071 (HP) — Supervisor revierte RETRASADO con nueva ubicación completa → 200."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_supervisor)
        assert resp.status_code == 200

    def test_cp0071_estado_vuelve_al_flujo_normal(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0071 (HP) — Tras revertir, el envío regresa al flujo normal."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_TRANSITO


# ── CP-0072 — Reversión con ubicación vacía o ausente es rechazada ───────────

class TestCP0072ReversionSinUbicacion:

    def test_cp0072_sin_ubicacion_ni_reusar_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0072 (UP) — Revertir sin nueva_ubicacion y reusar=false retorna 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        assert resp.status_code == 422

    def test_cp0072_calle_vacia_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0072 (UP) — Revertir con campos de ubicación vacíos retorna 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, "calle": ""},
        }, headers=headers_supervisor)
        assert resp.status_code == 422

    def test_cp0072_estado_permanece_en_excepcion(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0072 (UP) — El estado permanece en RETRASADO tras el intento fallido."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.RETRASADO


# ── CP-0068 — Reversión vuelve específicamente a EN_TRANSITO ─────────────────

class TestCP0068ReversionEstadoPrevioEnTransito:

    def test_cp0068_estado_revertir_apunta_a_en_transito(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0068 (HP) — Tras EN_TRANSITO→RETRASADO, estado_revertir vale EN_TRANSITO."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        detalle = client.get(f"/envios/{tid}", headers=headers_operador).json()
        assert detalle["estado_revertir"] == "EN_TRANSITO"

    def test_cp0068_reversion_lleva_a_en_transito_especificamente(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0068 (HP) — Revertir RETRASADO lleva al envío a EN_TRANSITO, no a otro estado."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_supervisor)
        assert resp.status_code == 200
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_TRANSITO


# ── CP-0323 — Reversión vuelve específicamente a EN_SUCURSAL ─────────────────

class TestCP0323ReversionEstadoPrevioEnSucursal:

    def test_cp0323_estado_revertir_apunta_a_en_sucursal(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0323 (HP) — Tras EN_SUCURSAL→BLOQUEADO, estado_revertir vale EN_SUCURSAL."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_SUCURSAL", headers_operador)
        _asignar_excepcion(client, tid, "BLOQUEADO", headers_supervisor)
        detalle = client.get(f"/envios/{tid}", headers=headers_operador).json()
        assert detalle["estado_revertir"] == "EN_SUCURSAL"

    def test_cp0323_reversion_lleva_a_en_sucursal_especificamente(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0323 (HP) — Revertir BLOQUEADO lleva al envío a EN_SUCURSAL, no a otro estado.

        EN_SUCURSAL es obligatorio: requiere nueva_ubicacion (no permite reusar).
        """
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_SUCURSAL", headers_operador)
        _asignar_excepcion(client, tid, "BLOQUEADO", headers_supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_SUCURSAL",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_supervisor)
        assert resp.status_code == 200
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_SUCURSAL


# ── CP-0073 — Reutilizar ubicación anterior al revertir ──────────────────────

class TestCP0073ReusoUbicacionEnReversion:

    def test_cp0073_reusar_ubicacion_al_revertir_retorna_200(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0073 (HP) — Supervisor revierte RETRASADO con reusar_ubicacion_anterior=true → 200.

        EN_TRANSITO no es obligatorio, por lo que reusar está permitido.
        La ubicación registrada en el paso anterior (RETRASADO) queda como última ubicación.
        """
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": True,
        }, headers=headers_supervisor)
        assert resp.status_code == 200

    def test_cp0073_estado_actualizado_al_reusar(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0073 (HP) — El estado queda en EN_TRANSITO tras reusar la ubicación."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": True,
        }, headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_TRANSITO

    def test_cp0073_evento_registra_ubicacion_anterior(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0073 (HP) — El evento de reversión reutiliza la misma ubicación que el evento de excepción.

        Setup con una sola ubicacion_actual_id en toda la cadena para evitar ambigüedad
        de orden cuando los timestamps coinciden en SQLite durante tests.
        """
        tid = _crear_envio(client, headers_operador)
        # Una única ubicación nueva en EN_DEPOSITO (todos los pasos siguientes reusarán la misma)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_DEPOSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_operador)
        # EN_DEPOSITO → RETRASADO reutilizando la ubicación anterior
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": True,
        }, headers=headers_supervisor)
        # RETRASADO → EN_TRANSITO reutilizando la ubicación anterior
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": True,
        }, headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento_retrasado = (db_session.query(EventoDeEnvio)
                            .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                                    EventoDeEnvio.estado_final == EstadoEnvioEnum.RETRASADO)
                            .first())
        evento_reversion = (db_session.query(EventoDeEnvio)
                            .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                                    EventoDeEnvio.estado_inicial == EstadoEnvioEnum.RETRASADO,
                                    EventoDeEnvio.estado_final == EstadoEnvioEnum.EN_TRANSITO)
                            .first())
        assert evento_reversion is not None
        assert evento_reversion.ubicacion_actual_id == evento_retrasado.ubicacion_actual_id


# ── CP-0074 — BLOQUEADO inválido desde EN_TRANSITO ───────────────────────────

class TestCP0074BloqueadoDesdeEnTransito:

    def test_cp0074_bloqueado_desde_en_transito_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0074 (UP) — BLOQUEADO no es una transición válida desde EN_TRANSITO → 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = _asignar_excepcion(client, tid, "BLOQUEADO", headers_supervisor)
        assert resp.status_code == 422

    def test_cp0074_estado_no_cambia(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0074 (UP) — El estado permanece EN_TRANSITO tras el intento fallido."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "BLOQUEADO", headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_TRANSITO


# ── CP-0324 — BLOQUEADO inválido desde EN_DISTRIBUCION ───────────────────────

class TestCP0324BloqueadoDesdeEnDistribucion:

    def test_cp0324_bloqueado_desde_en_distribucion_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0324 (UP) — BLOQUEADO no es una transición válida desde EN_DISTRIBUCION → 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_DISTRIBUCION", headers_operador)
        resp = _asignar_excepcion(client, tid, "BLOQUEADO", headers_supervisor)
        assert resp.status_code == 422

    def test_cp0324_estado_no_cambia(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0324 (UP) — El estado permanece EN_DISTRIBUCION tras el intento fallido."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_DISTRIBUCION", headers_operador)
        _asignar_excepcion(client, tid, "BLOQUEADO", headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.EN_DISTRIBUCION


# ── CP-0325 — BLOQUEADO válido desde EN_DEPOSITO ─────────────────────────────

class TestCP0325BloqueadoDesdeEnDeposito:

    def test_cp0325_bloqueado_desde_en_deposito_retorna_200(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0325 (HP) — BLOQUEADO es una transición válida desde EN_DEPOSITO → 200."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_DEPOSITO", headers_operador)
        resp = _asignar_excepcion(client, tid, "BLOQUEADO", headers_supervisor)
        assert resp.status_code == 200

    def test_cp0325_estado_actualizado_en_bd(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0325 (HP) — El estado queda en BLOQUEADO en la BD."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_DEPOSITO", headers_operador)
        _asignar_excepcion(client, tid, "BLOQUEADO", headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.BLOQUEADO


# ── CP-0326 — Registro de auditoría por cambio de excepción ──────────────────

class TestCP0326AuditoriaExcepcion:

    def test_cp0326_se_crea_evento_al_asignar_excepcion(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0326 (HP) — Asignar RETRASADO genera un EventoDeEnvio de CAMBIO_ESTADO."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.estado_final == EstadoEnvioEnum.RETRASADO)
                  .first())
        assert evento is not None

    def test_cp0326_evento_registra_estado_inicial_y_final(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0326 (HP) — El evento registra correctamente el estado anterior y el nuevo."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.estado_final == EstadoEnvioEnum.RETRASADO)
                  .first())
        assert evento.estado_inicial == EstadoEnvioEnum.EN_TRANSITO
        assert evento.estado_final   == EstadoEnvioEnum.RETRASADO

    def test_cp0326_evento_registra_ubicacion_y_fecha(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0326 (HP) — El evento registra ubicación y fecha_hora."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        _asignar_excepcion(client, tid, "RETRASADO", headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        evento = (db_session.query(EventoDeEnvio)
                  .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                          EventoDeEnvio.estado_final == EstadoEnvioEnum.RETRASADO)
                  .first())
        assert evento.ubicacion_actual_id is not None
        assert evento.fecha_hora is not None


# ── CP-0327 — Fallo de validación no genera evento de auditoría ──────────────

class TestCP0327AuditoriaNoRegistraFallo:

    def test_cp0327_evento_no_creado_si_ubicacion_invalida(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0327 (UP) — Un intento fallido por ubicación inválida no genera evento."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        cantidad_antes = (db_session.query(EventoDeEnvio)
                          .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                                  EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                          .count())
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": {**UBICACION_VALIDA, "calle": ""},
        }, headers=headers_supervisor)
        db_session.expire_all()
        cantidad_despues = (db_session.query(EventoDeEnvio)
                            .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                                    EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                            .count())
        assert cantidad_despues == cantidad_antes

    def test_cp0327_evento_no_creado_si_transicion_invalida(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0327 (UP) — Un intento fallido por transición inválida no genera evento."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        cantidad_antes = (db_session.query(EventoDeEnvio)
                          .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                                  EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                          .count())
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "BLOQUEADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_supervisor)
        db_session.expire_all()
        cantidad_despues = (db_session.query(EventoDeEnvio)
                            .filter(EventoDeEnvio.envio_uuid == envio.uuid,
                                    EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO)
                            .count())
        assert cantidad_despues == cantidad_antes


# ── CP-0328 — DELETE en envío CANCELADO retorna 200 ──────────────────────────

class TestCP0328DeleteCancelado:

    def test_cp0328_delete_cancelado_retorna_200(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0328 (HP) — DELETE sobre envío CANCELADO retorna 200."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "CANCELADO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        resp = client.delete(f"/envios/{tid}", headers=headers_supervisor)
        assert resp.status_code == 200

    def test_cp0328_estado_pasa_a_eliminado(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0328 (HP) — Tras el DELETE, el estado del envío es ELIMINADO."""
        tid = _crear_envio(client, headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "CANCELADO",
            "reusar_ubicacion_anterior": False,
        }, headers=headers_supervisor)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.ELIMINADO


# ── CP-0329 — DELETE en envío no CANCELADO retorna 422 ───────────────────────

class TestCP0329DeleteNoCancelado:

    def test_cp0329_delete_en_registrado_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0329 (UP) — DELETE sobre envío en REGISTRADO retorna 422."""
        tid = _crear_envio(client, headers_operador)
        resp = client.delete(f"/envios/{tid}", headers=headers_supervisor)
        assert resp.status_code == 422

    def test_cp0329_delete_en_transito_retorna_422(
        self, client, headers_operador, headers_supervisor
    ):
        """CP-0329 (UP) — DELETE sobre envío en EN_TRANSITO retorna 422."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = client.delete(f"/envios/{tid}", headers=headers_supervisor)
        assert resp.status_code == 422

    def test_cp0329_estado_no_cambia_tras_delete_fallido(
        self, client, db_session, headers_operador, headers_supervisor
    ):
        """CP-0329 (UP) — El estado permanece REGISTRADO tras el intento de DELETE fallido."""
        tid = _crear_envio(client, headers_operador)
        client.delete(f"/envios/{tid}", headers=headers_supervisor)
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        assert envio.estado == EstadoEnvioEnum.REGISTRADO


# ── CP-0062 / CP-0063 / CP-0070 — control de acceso ─────────────────────────

class TestCP0062CP0063CP0070ControlAccesoExcepcion:

    def test_cp0062_admin_no_puede_asignar_excepcion_retorna_403(self, client, headers_operador, headers_admin):
        """CP-0062 (UP) — CA-1: JWT con rol Administrador recibe 403 al asignar estado de excepción."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_admin)
        assert resp.status_code == 403

    def test_cp0063_sin_token_retorna_401_al_asignar_excepcion(self, client, headers_operador):
        """CP-0063 (EC) — CA-1: Request sin header Authorization retorna 401 al asignar estado de excepción."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        assert resp.status_code == 401

    def test_cp0070_sin_token_retorna_401_al_revertir_excepcion(self, client, headers_operador, headers_supervisor):
        """CP-0070 (EC) — CA-5: Request sin header Authorization retorna 401 al revertir estado de excepción."""
        tid = _crear_envio(client, headers_operador)
        _avanzar_hasta(client, tid, "EN_TRANSITO", headers_operador)
        client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "RETRASADO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        }, headers=headers_supervisor)
        resp = client.patch(f"/envios/{tid}/estado", json={
            "nuevo_estado": "EN_TRANSITO",
            "reusar_ubicacion_anterior": False,
            "nueva_ubicacion": UBICACION_VALIDA,
        })
        assert resp.status_code == 401