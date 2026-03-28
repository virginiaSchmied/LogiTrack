# Implementación del módulo ML (LP-111 a LP-119)

## Objetivo

Clasificar automáticamente la prioridad de cada envío en **ALTA / MEDIA / BAJA** usando un modelo de ML entrenado sobre datos históricos, eliminando la subjetividad del proceso manual.

### Columnas clave en la BD

| Campo | Tabla | Tipo | Rol |
|---|---|---|---|
| `probabilidad_retraso` | `envio` | `Numeric(5,2)` | Feature — ingresada por el operador |
| `fecha_entrega_estimada` | `envio` | `Date` | Se usa para calcular `dias_para_entrega` |
| `prioridad` | `envio` | `NivelPrioridadEnum` | Target (ALTA / MEDIA / BAJA) |

`dias_para_entrega` = `fecha_entrega_estimada - date.today()` calculado en el momento de la predicción (no se persiste). Valores negativos se tratan como 0.

---

## Regla de negocio (matriz prioridad)

```
                    dias_para_entrega
                  ≤ 2 días   3-7 días   > 7 días
               ┌──────────┬──────────┬──────────┐
 prob > 0.70   │  ALTA    │  ALTA    │  MEDIA   │
 0.40 - 0.70   │  ALTA    │  MEDIA   │  MEDIA   │
 prob < 0.40   │  MEDIA   │  BAJA    │  BAJA    │
               └──────────┴──────────┴──────────┘
```

**Lectura intuitiva:**
- Alta probabilidad de retraso + poco tiempo → siempre ALTA
- Alta probabilidad de retraso + mucho margen → MEDIA (hay tiempo para actuar)
- Baja probabilidad de retraso + poco tiempo → MEDIA (la urgencia del plazo importa)
- Baja probabilidad de retraso + mucho margen → BAJA

---

## LP-111 — Curación del dataset ✅

**Implementado:** `db/migrations/insert_datos_iniciales.sql` contiene 24 envíos que cubren los 9 cuadrantes de la matriz con prioridades correctamente etiquetadas.

Para exportar los datos reales a CSV desde la BD:
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

Guardar resultado como `ml/dataset/dataset_inicial.csv`.

**Entregable:** `ml/dataset/dataset_inicial.csv` — 23 registros reales versionados en el repositorio.

---

## LP-112 — Script de data augmentation ✅

**Implementado:** `ml/dataset/generar_dataset.py`

El script:
1. Lee `ml/dataset/dataset_inicial.csv` (datos reales)
2. Genera 2000 filas sintéticas dividiendo el espacio en los 9 cuadrantes de la matriz
3. Aplica ruido gaussiano (σ=0.05 en probabilidad, σ=1 en días) para simular variabilidad real
4. Combina reales + sintéticos, los baraja con semilla fija (`random.seed(42)`) y exporta

```bash
python3 ml/dataset/generar_dataset.py
# → genera ml/dataset/dataset_aumentado.csv (~2023 filas)
```

**Entregable:** `ml/dataset/dataset_aumentado.csv` — versionado en el repositorio.

---

## LP-114 — Selección y comparación de algoritmos ✅

**Implementado en:** `ml/train.py`

Se evaluaron 3 algoritmos con split 80/20 y `random_state=42`:

| Algoritmo | Accuracy | F1-score macro |
|---|---|---|
| **Decision Tree** | **1.0000** | **1.0000** |
| Random Forest | 1.0000 | 1.0000 |
| K-Nearest Neighbors | 0.9407 | 0.9356 |

**Algoritmo seleccionado: Decision Tree** — elegido por mayor interpretabilidad ante métricas equivalentes a Random Forest. Sus decisiones pueden representarse como un árbol de condiciones legibles, lo que facilita la validación de que el modelo aprendió correctamente la regla de negocio.

**Entregables:** imágenes comparativas en `ml/reportes/` (generadas al correr `train.py`).

---

## LP-115 — Entrenamiento y métricas finales ✅

**Implementado en:** `ml/train.py`

El script:
1. Carga `ml/dataset/dataset_aumentado.csv`
2. Divide 80/20 con `random_state=42` y `stratify=y`
3. Entrena y evalúa los 3 algoritmos candidatos
4. Reentrena el ganador sobre el **100% del dataset** antes de exportar
5. Genera tablas de métricas y matrices de confusión como imágenes PNG

```bash
python3 ml/train.py
```

**Entregables:** `ml/reportes/reporte_*.png`, `ml/reportes/confusion_*.png`, `ml/reportes/comparacion_algoritmos.png`

---

## LP-116 — Exportar modelo ✅

**Implementado en:** `ml/train.py` (función `exportar`)

- Modelo serializado con `joblib.dump` → `ml/modelo_prioridad.joblib`
- Verificación automática al exportar: carga el modelo y predice un caso de prueba
- Modelo versionado en el repositorio

**Para regenerar el modelo:**
```bash
python3 ml/dataset/generar_dataset.py
python3 ml/train.py
```

**Entregable:** `ml/modelo_prioridad.joblib` — versionado en el repositorio.

---

## LP-117 — Servicio de predicción ✅

**Implementado en:** `backend/ml_predictor.py`

- Carga el modelo una sola vez al iniciar la app (singleton)
- Si el modelo no existe, loguea un warning y retorna `None` sin romper el flujo
- Expone `predecir_prioridad(probabilidad_retraso, dias_para_entrega) → str | None`

**Pendiente (requiere endpoint de update — otra US):**
- LP-117 CA-5: recalcular prioridad al modificar `probabilidad_retraso`
- LP-117 CA-6: recalcular prioridad al modificar `fecha_entrega_estimada`

---

## LP-118 — Persistir prioridad en la BD ✅ (parcial)

**Implementado en:** `backend/routers/envios.py` (POST /envios/)

Al crear un envío:
1. Si `probabilidad_retraso` está presente, calcula `dias_para_entrega = max(0, (fecha_entrega_estimada - date.today()).days)`
2. Llama a `predecir_prioridad()` del módulo `ml_predictor`
3. Persiste el resultado en `envio.prioridad` en el mismo `commit`
4. Si el modelo no está disponible, `prioridad` queda `NULL`

**Pendiente (requiere endpoint de update — otra US):**
- LP-118 CA-2: recalcular al modificar `probabilidad_retraso`
- LP-118 CA-3: recalcular al modificar `fecha_entrega_estimada`

---

## LP-119 — Visualización en el frontend ✅

**Implementado en:** `frontend/app.js`, `frontend/index.html`, `frontend/style.css`

- Columna **Prioridad** en la tabla de listado con badge de color
- Badge de prioridad en el modal de detalle
- Campo opcional **Probabilidad de retraso** en el formulario de alta
- Si `prioridad` es `null` → muestra badge gris **"Sin clasificar"**

Colores:
- ALTA → rojo
- MEDIA → amarillo
- BAJA → verde
- Sin prioridad → gris

---

## Estructura de archivos

```
LogiTrack/
├── ml/
│   ├── dataset/
│   │   ├── exportar_desde_db.py     # Exporta datos reales de la BD
│   │   ├── generar_dataset.py       # Genera dataset sintético aumentado
│   │   ├── dataset_inicial.csv      # Datos reales (versionado)
│   │   └── dataset_aumentado.csv    # Dataset completo (versionado)
│   ├── reportes/                    # Imágenes de métricas (generadas localmente)
│   ├── train.py                     # Entrenamiento, evaluación y exportación
│   ├── modelo_prioridad.joblib      # Modelo serializado (versionado)
│   └── README.md                    # Documentación técnica del modelo
├── backend/
│   ├── ml_predictor.py              # Servicio de predicción (LP-117)
│   └── routers/
│       └── envios.py                # Integración ML en POST /envios/ (LP-118)
└── ML_IMPLEMENTACION.md             # Este archivo
```

## Dependencias agregadas al backend

```
scikit-learn>=1.4
joblib>=1.3
numpy>=1.26
```
