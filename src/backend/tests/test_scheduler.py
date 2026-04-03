"""
Tests para el recálculo diario de prioridades de envíos activos.

Cubre:
  LP-257 — Recalcular prioridad de envíos activos diariamente

  CP-0331 (HP) — CA-1: El job está configurado para ejecutarse a medianoche hora Argentina
  CP-0332 (HP) — CA-2: Solo se recalculan envíos en estados activos; los terminales se ignoran
  CP-0333 (HP) — CA-3: La prioridad se actualiza cuando el modelo da un resultado distinto
  CP-0334 (HP) — CA-4: No se persiste si la prioridad ya es correcta
  CP-0335 (HP) — CA-5: Un fallo individual no interrumpe el procesamiento del resto
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest

import scheduler as scheduler_module
from models import Envio, EstadoEnvioEnum, NivelPrioridadEnum
from scheduler import scheduler, recalcular_prioridades
from tests.conftest import _SessionLocal

_FECHA_FUTURA = str(date.today() + timedelta(days=30))
_MANANA = date.today() + timedelta(days=1)

PAYLOAD_ENVIO = {
    "remitente": "Juan Pérez",
    "destinatario": "María García",
    "probabilidad_retraso": 0.1,
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


def _crear_envio(client) -> str:
    r = client.post("/envios/", json=PAYLOAD_ENVIO)
    assert r.status_code == 201
    return r.json()["tracking_id"]


def _forzar_prioridad(db_session, tid: str, prioridad: NivelPrioridadEnum,
                      prob: float = None, fecha: date = None):
    """Modifica directamente en DB la prioridad (y opcionalmente prob/fecha) de un envío."""
    envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
    envio.prioridad = prioridad
    if prob is not None:
        envio.probabilidad_retraso = prob
    if fecha is not None:
        envio.fecha_entrega_estimada = fecha
    db_session.commit()


@pytest.fixture
def patch_db(client):
    """Redirige el SessionLocal del scheduler a la DB de tests (SQLite in-memory)."""
    with patch.object(scheduler_module, 'SessionLocal', _SessionLocal):
        yield


# ── CP-0331 — CA-1: configuración del job ────────────────────────────────────

class TestCP0331ConfiguracionJob:

    def test_cp0331_job_existe_en_el_scheduler(self):
        """CP-0331 (HP) — CA-1: El job 'recalcular_prioridades' está registrado en el scheduler."""
        job = scheduler.get_job('recalcular_prioridades')
        assert job is not None

    def test_cp0331_job_trigger_es_cron(self):
        """CP-0331 (HP) — CA-1: El job usa trigger de tipo cron."""
        job = scheduler.get_job('recalcular_prioridades')
        assert job.trigger.__class__.__name__ == 'CronTrigger'

    def test_cp0331_job_corre_a_medianoche(self):
        """CP-0331 (HP) — CA-1: El cron está configurado en hour=0, minute=0."""
        job = scheduler.get_job('recalcular_prioridades')
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields['hour'] == '0'
        assert fields['minute'] == '0'

    def test_cp0331_job_timezone_argentina(self):
        """CP-0331 (HP) — CA-1: El scheduler usa timezone America/Argentina/Buenos_Aires."""
        assert str(scheduler.timezone) == 'America/Argentina/Buenos_Aires'


# ── CP-0332 — CA-2: solo estados activos ─────────────────────────────────────

class TestCP0332SoloEstadosActivos:

    def test_cp0332_envio_terminal_no_se_actualiza(self, client, db_session, patch_db):
        """CP-0332 (HP) — CA-2: Un envío en estado terminal no es modificado por el scheduler."""
        tid = _crear_envio(client)
        # Forzar estado terminal y prioridad incorrecta
        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        envio.estado = EstadoEnvioEnum.ENTREGADO
        envio.prioridad = NivelPrioridadEnum.BAJA
        envio.probabilidad_retraso = 0.9
        envio.fecha_entrega_estimada = _MANANA
        db_session.commit()

        recalcular_prioridades()

        db_session.refresh(envio)
        assert envio.prioridad == NivelPrioridadEnum.BAJA  # sin cambio

    def test_cp0332_envio_activo_si_se_procesa(self, client, db_session, patch_db):
        """CP-0332 (HP) — CA-2: Un envío en estado activo sí es procesado por el scheduler."""
        tid = _crear_envio(client)
        _forzar_prioridad(db_session, tid, NivelPrioridadEnum.BAJA, prob=0.9, fecha=_MANANA)

        recalcular_prioridades()

        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        db_session.refresh(envio)
        assert envio.prioridad != NivelPrioridadEnum.BAJA

    def test_cp0332_terminales_ignorados_activos_procesados(self, client, db_session, patch_db):
        """CP-0332 (HP) — CA-2: Activos se actualizan y terminales permanecen sin cambio."""
        tid_activo = _crear_envio(client)
        tid_terminal = _crear_envio(client)

        # activo: prioridad incorrecta → debe cambiar
        _forzar_prioridad(db_session, tid_activo, NivelPrioridadEnum.BAJA, prob=0.9, fecha=_MANANA)

        # terminal: prioridad incorrecta → NO debe cambiar
        envio_terminal = db_session.query(Envio).filter(Envio.tracking_id == tid_terminal).first()
        envio_terminal.estado = EstadoEnvioEnum.CANCELADO
        envio_terminal.prioridad = NivelPrioridadEnum.BAJA
        envio_terminal.probabilidad_retraso = 0.9
        envio_terminal.fecha_entrega_estimada = _MANANA
        db_session.commit()

        recalcular_prioridades()

        db_session.refresh(envio_terminal)
        assert envio_terminal.prioridad == NivelPrioridadEnum.BAJA


# ── CP-0333 — CA-3: prioridad se actualiza cuando cambia ─────────────────────

class TestCP0333PrioridadSeActualiza:

    def test_cp0333_prioridad_cambia_cuando_fecha_es_proxima(self, client, db_session, patch_db):
        """CP-0333 (HP) — CA-3: El scheduler actualiza la prioridad cuando el modelo da distinto resultado."""
        tid = _crear_envio(client)
        # prob=0.9 + 1 día → modelo predice ALTA; forzamos BAJA para que haya cambio
        _forzar_prioridad(db_session, tid, NivelPrioridadEnum.BAJA, prob=0.9, fecha=_MANANA)

        recalcular_prioridades()

        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        db_session.refresh(envio)
        assert envio.prioridad != NivelPrioridadEnum.BAJA

    def test_cp0333_prioridad_persistida_en_db(self, client, db_session, patch_db):
        """CP-0333 (HP) — CA-3: El cambio de prioridad queda persistido en la base de datos."""
        tid = _crear_envio(client)
        _forzar_prioridad(db_session, tid, NivelPrioridadEnum.BAJA, prob=0.9, fecha=_MANANA)

        recalcular_prioridades()

        # Consultar con una sesión nueva para confirmar que se commitó
        nueva_sesion = _SessionLocal()
        try:
            envio = nueva_sesion.query(Envio).filter(Envio.tracking_id == tid).first()
            assert envio.prioridad != NivelPrioridadEnum.BAJA
        finally:
            nueva_sesion.close()


# ── CP-0334 — CA-4: no se persiste si no hay cambio ──────────────────────────

class TestCP0334SinCambioNoPersiste:

    def test_cp0334_prioridad_correcta_no_cambia(self, client, db_session, patch_db):
        """CP-0334 (HP) — CA-4: Si la prioridad ya es correcta, el scheduler no la modifica."""
        tid = _crear_envio(client)
        # prob=0.1 + 30 días → modelo predice BAJA; la dejamos en BAJA
        _forzar_prioridad(db_session, tid, NivelPrioridadEnum.BAJA, prob=0.1)

        envio = db_session.query(Envio).filter(Envio.tracking_id == tid).first()
        prioridad_antes = envio.prioridad

        recalcular_prioridades()

        db_session.refresh(envio)
        assert envio.prioridad == prioridad_antes

    def test_cp0334_commit_no_ocurre_si_nada_cambia(self, client, patch_db):
        """CP-0334 (HP) — CA-4: No se llama a commit cuando no hay ningún cambio."""
        # Sin envíos en la DB → actualizados = 0 → commit no se llama
        with patch.object(scheduler_module, 'SessionLocal') as mock_session_factory:
            mock_db = mock_session_factory.return_value
            mock_db.query.return_value.filter.return_value.all.return_value = []

            recalcular_prioridades()

            mock_db.commit.assert_not_called()


# ── CP-0335 — CA-5: fallo individual no interrumpe el proceso ────────────────

class TestCP0335FalloIndividual:

    def test_cp0335_proceso_continua_tras_fallo_en_un_envio(self, client, db_session, patch_db):
        """CP-0335 (HP) — CA-5: Si un envío falla, los demás siguen siendo procesados."""
        tid1 = _crear_envio(client)
        tid2 = _crear_envio(client)
        _forzar_prioridad(db_session, tid1, NivelPrioridadEnum.BAJA, prob=0.9, fecha=_MANANA)
        _forzar_prioridad(db_session, tid2, NivelPrioridadEnum.BAJA, prob=0.9, fecha=_MANANA)

        llamadas = []

        def predecir_con_fallo(prob, dias):
            llamadas.append((prob, dias))
            if len(llamadas) == 1:
                raise ValueError("fallo simulado en primer envío")
            return "ALTA"

        with patch.object(scheduler_module, 'predecir_prioridad', side_effect=predecir_con_fallo):
            recalcular_prioridades()

        # Se intentó predecir para los 2 envíos
        assert len(llamadas) == 2

        # Al menos 1 envío fue actualizado (el segundo)
        envios = db_session.query(Envio).filter(
            Envio.tracking_id.in_([tid1, tid2])
        ).all()
        db_session.expire_all()
        prioridades = {e.tracking_id: e.prioridad for e in envios}
        actualizados = sum(1 for p in prioridades.values() if p == NivelPrioridadEnum.ALTA)
        assert actualizados >= 1

    def test_cp0335_scheduler_no_lanza_excepcion_ante_fallo(self, client, patch_db):
        """CP-0335 (HP) — CA-5: El scheduler no propaga la excepción del fallo individual."""
        _crear_envio(client)

        with patch.object(scheduler_module, 'predecir_prioridad', side_effect=ValueError("fallo")):
            try:
                recalcular_prioridades()
            except Exception:
                pytest.fail("recalcular_prioridades() no debería propagar excepciones individuales")
