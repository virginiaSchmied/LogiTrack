# Módulo ML — LogiTrack SFGLD

Este documento describe el diseño, implementación y estado del módulo de clasificación automática de prioridad de envíos mediante Machine Learning.

---

## Objetivo

Clasificar automáticamente la prioridad de cada envío en **ALTA / MEDIA / BAJA** usando un modelo entrenado sobre datos históricos, eliminando la subjetividad del proceso manual y permitiendo al equipo logístico enfocar sus recursos en los envíos de mayor riesgo.

---

## 1. Definición del dataset

### Features y variable objetivo

| Campo | Tipo | Descripción |
|---|---|---|
| `probabilidad_retraso` | float [0.0, 1.0] | Probabilidad de retraso, ingresada por el operador al crear el envío |
| `dias_para_entrega` | int ≥ 0 | `fecha_entrega_estimada − fecha_actual` al momento de la predicción. Valores negativos se tratan como 0. No se persiste en la BD. |
| `prioridad` | ALTA / MEDIA / BAJA | Variable objetivo |

### Regla de negocio (matriz de prioridad)

La prioridad resulta de la combinación de ambas features en una matriz de 3×3:

```
                    dias_para_entrega
                  ≤ 2 días   3-7 días   > 7 días
               ┌──────────┬──────────┬──────────┐
 prob > 0.70   │  ALTA    │  ALTA    │  MEDIA   │
 0.40 - 0.70   │  ALTA    │  MEDIA   │  MEDIA   │
 prob < 0.40   │  MEDIA   │  BAJA    │  BAJA    │
               └──────────┴──────────┴──────────┘
```

---

## 2. Dataset

### Datos reales

Se insertaron 24 envíos en `src/db/migrations/insert_datos_iniciales.sql` cubriendo los 9 cuadrantes de la matriz con prioridades correctamente etiquetadas. Los datos se exportaron a CSV con la siguiente query:

```sql
SELECT
    CAST(probabilidad_retraso AS FLOAT)                AS probabilidad_retraso,
    (fecha_entrega_estimada - created_at::date)::int   AS dias_para_entrega,
    prioridad
FROM envio
WHERE probabilidad_retraso IS NOT NULL
  AND prioridad IS NOT NULL
  AND estado != 'ELIMINADO';
```

**Entregable:** `ml/dataset/dataset_inicial.csv` — 23 registros reales.

### Data augmentation

El script `ml/dataset/generar_dataset.py` (semilla `random.seed(42)`) genera 2000 filas sintéticas:

1. Lee `dataset_inicial.csv`
2. Muestrea aleatoriamente uno de los 9 cuadrantes por fila
3. Aplica ruido gaussiano (σ=0.05 sobre `probabilidad_retraso`, σ=1 sobre `dias_para_entrega`)
4. Combina reales + sintéticos y los baraja
5. Exporta `ml/dataset/dataset_aumentado.csv`

```bash
python3 ml/dataset/generar_dataset.py
```

**Entregable:** `ml/dataset/dataset_aumentado.csv` — 2023 filas. Distribución: ALTA ~30% / MEDIA ~47% / BAJA ~23%.

---

## 3. Selección de algoritmo

Se evaluaron 3 algoritmos con split 80/20 y `random_state=42`:

| Algoritmo | Accuracy | F1-score macro |
|---|---|---|
| **Decision Tree** | **1.0000** | **1.0000** |
| Random Forest | 1.0000 | 1.0000 |
| K-Nearest Neighbors | 0.9407 | 0.9356 |

**Algoritmo seleccionado: Decision Tree.**

Decision Tree y Random Forest obtuvieron métricas perfectas. Se eligió Decision Tree por mayor interpretabilidad: sus decisiones se representan como un árbol de condiciones legibles, lo que facilita validar que el modelo aprendió correctamente la regla de negocio.

**Evidencia:** `ml/reportes/comparacion_algoritmos.png`

---

## 4. Entrenamiento y métricas

Implementado en `ml/train.py`. El script evalúa los 3 algoritmos sobre el 20% de test y exporta directamente el modelo ganador **sin reentrenar sobre el dataset completo**. De esta forma, las métricas reportadas corresponden exactamente al modelo guardado en producción.

**Métricas del modelo final (evaluadas sobre el 20% de test):**

| Clase | Precision | Recall | F1-score |
|---|---|---|---|
| ALTA | 1.00 | 1.00 | 1.00 |
| MEDIA | 1.00 | 1.00 | 1.00 |
| BAJA | 1.00 | 1.00 | 1.00 |
| **macro avg** | **1.00** | **1.00** | **1.00** |

**Evidencia:**
- `ml/reportes/reporte_decisiontree.png` — tabla de métricas por clase
- `ml/reportes/confusion_decisiontree.png` — matriz de confusión

Para reproducir los resultados:

```bash
python3 ml/dataset/generar_dataset.py  # semilla: random.seed(42)
python3 ml/train.py                    # semilla: RANDOM_STATE=42
```

---

## 5. Exportación y validación del modelo

El modelo fue serializado con `joblib.dump` al finalizar `train.py`. Al exportar, el script ejecuta automáticamente una tabla de validación con 9 casos fijos que cubren los 9 cuadrantes de la matriz de prioridad. Cada caso compara el resultado esperado con el predicho e indica si hay discrepancias:

```
============================================================
VALIDACIÓN DEL MODELO (matriz de prioridad completa)
============================================================
  prob   dias    esperado    predicho    ok
  ----   ----   ----------  ----------  ----
  0.85      1        ALTA        ALTA     ✓
  0.85      5        ALTA        ALTA     ✓
  0.85     10       MEDIA       MEDIA     ✓
  0.55      1        ALTA        ALTA     ✓
  0.55      5       MEDIA       MEDIA     ✓
  0.55     10       MEDIA       MEDIA     ✓
  0.20      1       MEDIA       MEDIA     ✓
  0.20      5        BAJA        BAJA     ✓
  0.20     10        BAJA        BAJA     ✓
============================================================
Todos los casos correctos. El modelo reproduce la matriz de prioridad.
```

Los valores de entrada son fijos y no dependen de fechas, por lo que la validación es reproducible en cualquier momento.

**Entregable:** `ml/modelo_prioridad.joblib` — versionado en el repositorio.

---

## 6. Servicio de predicción 

Implementado en `src/backend/ml_predictor.py`:

- Carga el modelo una sola vez al iniciar la aplicación (singleton)
- Expone `predecir_prioridad(probabilidad_retraso, dias_para_entrega) → str | None`
- Si el modelo no está disponible, loguea un warning y retorna `None` sin interrumpir el flujo

---

## 7. Persistencia de prioridad

Integrado en `src/backend/routers/envios.py` (`POST /envios/`):

1. Si `probabilidad_retraso` está presente en el payload, calcula `dias_para_entrega = max(0, (fecha_entrega_estimada − date.today()).days)`
2. Llama a `predecir_prioridad()` y persiste el resultado en `envio.prioridad`
3. Si el modelo no está disponible, `prioridad` queda `NULL` sin romper el flujo
4. La prioridad no es editable manualmente desde ninguna pantalla

---

## 8. Visualización en el frontend

Cambios en `src/frontend/`:

- Columna **Prioridad** en la tabla de listado con badge de color
- Badge de prioridad en el modal de detalle del envío
- Campo opcional **Probabilidad de retraso** en el formulario de alta
- Envíos sin prioridad asignada muestran el badge gris **"Sin clasificar"**

| Prioridad | Color |
|---|---|
| ALTA | Rojo |
| MEDIA | Amarillo |
| BAJA | Verde |
| Sin asignar | Gris |

---

## Estructura de archivos

```
src/
├── backend/
│   ├── ml_predictor.py              # Servicio de predicción (LP-117)
│   └── routers/
│       └── envios.py                # Integración ML en POST /envios/ (LP-118)
└── ml/
    ├── dataset/
    │   ├── exportar_desde_db.py     # Exporta datos reales de la BD
    │   ├── generar_dataset.py       # Genera dataset sintético aumentado
    │   ├── dataset_inicial.csv      # Datos reales (versionado)
    │   └── dataset_aumentado.csv    # Dataset completo (versionado)
    ├── reportes/
    │   ├── comparacion_algoritmos.png
    │   ├── reporte_decisiontree.png
    │   └── confusion_decisiontree.png
    ├── train.py                     # Entrenamiento, evaluación y exportación
    └── modelo_prioridad.joblib      # Modelo serializado (versionado)
```
