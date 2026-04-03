"""
Scheduler de tareas programadas — LogiTrack.

Usa APScheduler (BackgroundScheduler) integrado con el ciclo de vida de FastAPI.
El scheduler se inicia al arrancar el servidor y se detiene al cerrarlo.

Tareas registradas:
  - recalcular_prioridades: corre todos los días a medianoche.
    Recalcula la prioridad de todos los envíos activos usando el modelo ML,
    ya que 'dias_para_entrega' cambia con el paso del tiempo.
"""

import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from models import Envio, EstadoEnvioEnum, NivelPrioridadEnum
from ml_predictor import predecir_prioridad

logger = logging.getLogger(__name__)

# Estados donde la prioridad sigue siendo relevante
_ESTADOS_ACTIVOS = [
    EstadoEnvioEnum.REGISTRADO,
    EstadoEnvioEnum.EN_DEPOSITO,
    EstadoEnvioEnum.EN_TRANSITO,
    EstadoEnvioEnum.EN_SUCURSAL,
    EstadoEnvioEnum.EN_DISTRIBUCION,
    EstadoEnvioEnum.RETRASADO,
    EstadoEnvioEnum.BLOQUEADO,
]


def recalcular_prioridades():
    """
    Recalcula la prioridad de todos los envíos activos con el modelo ML.

    Itera los envíos en estados activos y actualiza el campo 'prioridad'
    cuando el resultado del modelo difiere del valor almacenado.
    Los días para entrega se recalculan contra la fecha actual.
    """
    logger.info("Iniciando recálculo diario de prioridades")
    db = SessionLocal()
    try:
        envios = db.query(Envio).filter(Envio.estado.in_(_ESTADOS_ACTIVOS)).all()
        actualizados = 0

        for envio in envios:
            dias = max((envio.fecha_entrega_estimada - date.today()).days, 0)
            try:
                resultado = predecir_prioridad(float(envio.probabilidad_retraso), dias)
                nueva_prioridad = NivelPrioridadEnum(resultado)
            except (ValueError, RuntimeError) as e:
                logger.warning("No se pudo predecir prioridad para %s: %s", envio.tracking_id, e)
                continue

            if envio.prioridad != nueva_prioridad:
                envio.prioridad = nueva_prioridad
                actualizados += 1

        if actualizados:
            db.commit()
        logger.info("Recálculo de prioridades completado: %d envíos actualizados de %d", actualizados, len(envios))

    except Exception as e:
        logger.error("Error en recálculo de prioridades: %s", e)
        db.rollback()
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone="America/Argentina/Buenos_Aires")
scheduler.add_job(
    recalcular_prioridades,
    trigger="cron",
    hour=0,
    minute=0,
    id="recalcular_prioridades",
    replace_existing=True,
)
