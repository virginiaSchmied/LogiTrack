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
        probabilidad_retraso: float entre 0.0 y 1.0
        dias_para_entrega:    int >= 0, días hasta la fecha estimada de entrega

    Returns:
        "ALTA", "MEDIA" o "BAJA", o None si el modelo no está disponible.

    Raises:
        ValueError: si alguna feature es inválida o está fuera de rango.
    """
    if not isinstance(probabilidad_retraso, (int, float)):
        raise ValueError(
            f"'probabilidad_retraso' debe ser un número (float), "
            f"se recibió {type(probabilidad_retraso).__name__}."
        )
    if not (0.0 <= float(probabilidad_retraso) <= 1.0):
        raise ValueError(
            f"'probabilidad_retraso' debe estar entre 0.0 y 1.0, "
            f"se recibió {probabilidad_retraso}."
        )
    if not isinstance(dias_para_entrega, (int, float)):
        raise ValueError(
            f"'dias_para_entrega' debe ser un número entero, "
            f"se recibió {type(dias_para_entrega).__name__}."
        )
    if int(dias_para_entrega) < 0:
        raise ValueError(
            f"'dias_para_entrega' debe ser >= 0, "
            f"se recibió {dias_para_entrega}."
        )

    if _modelo is None:
        raise RuntimeError(
            "El modelo ML no está disponible. "
            "Ejecutá ml/train.py para generarlo."
        )

    X = np.array([[float(probabilidad_retraso), int(dias_para_entrega)]])
    return str(_modelo.predict(X)[0])
