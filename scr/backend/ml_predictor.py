"""
LP-117 — Servicio de predicción de prioridad de envíos.

Carga el modelo entrenado una sola vez al importar el módulo
y expone predecir_prioridad() para uso interno desde los routers.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "ml" / "modelo_prioridad.joblib"

_modelo = None


def _cargar_modelo():
    global _modelo
    if _modelo is not None:
        return
    if not MODEL_PATH.exists():
        logger.warning(
            "Modelo ML no encontrado en %s. "
            "La prioridad no se asignará automáticamente. "
            "Ejecutá ml/train.py para generar el modelo.",
            MODEL_PATH,
        )
        return
    try:
        import joblib
        _modelo = joblib.load(MODEL_PATH)
        logger.info("Modelo ML cargado desde %s", MODEL_PATH)
    except Exception as e:
        logger.error("Error al cargar el modelo ML: %s", e)


_cargar_modelo()


def predecir_prioridad(probabilidad_retraso: float, dias_para_entrega: int) -> Optional[str]:
    """
    Predice la prioridad de un envío.

    Args:
        probabilidad_retraso: float entre 0 y 1
        dias_para_entrega:    días hasta la fecha estimada de entrega (mínimo 0)

    Returns:
        "ALTA", "MEDIA" o "BAJA", o None si el modelo no está disponible.
    """
    if _modelo is None:
        return None

    dias = max(0, dias_para_entrega)
    X = np.array([[probabilidad_retraso, dias]])
    return str(_modelo.predict(X)[0])
