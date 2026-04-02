# LogiTrack — Sistema Federal de Gestión de Logística y Distribución (SFGLD)

LogiTrack es un sistema web diseñado para centralizar y gestionar operaciones logísticas y de distribución a nivel federal. Forma parte del **TP Inicial** de la materia **Laboratorio de Construccion de Software** cuyo objetivo es la creación de un **Paquete Base reutilizable** que sirva como fundación para futuras extensiones del sistema.

---

## Características principales

- Registro y seguimiento de envíos
- Gestión de usuarios y roles
- Consulta de estado y detalle de envíos
- API REST documentada (FastAPI + Swagger UI)
- Migraciones de base de datos versionadas
- Suite de tests unitarios y end-to-end

---

## Tecnologías

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11, FastAPI |
| Base de datos | PostgreSQL |
| Frontend | HTML5, CSS3, JavaScript (Vanilla) |
| Machine Learning | scikit-learn (Decision Tree) |
| Tests unitarios | pytest |
| Tests E2E | Playwright |
| Control de versiones | Git / GitHub |

---

## Estructura del proyecto

```
LogiTrack/
├── src/
│   ├── backend/
│   │   ├── main.py               # Entry point FastAPI
│   │   ├── models.py             # Modelos ORM (SQLAlchemy)
│   │   ├── schemas.py            # Schemas Pydantic
│   │   ├── database.py           # Conexión y sesión de DB
│   │   ├── ml_predictor.py       # Predicción de prioridad
│   │   ├── routers/
│   │   │   └── envios.py         # Todos los endpoints de envíos
│   │   └── tests/                # Tests unitarios
│   ├── db/
│   │   └── migrations/           # Scripts SQL de migración
│   ├── frontend/
│   │   ├── index.html
│   │   ├── app.js
│   │   └── style.css
│   └── ml/
│       ├── train.py              # Entrena Decision Tree y exporta .joblib
│       ├── evaluar_modelos.py    # Compara Decision Tree, Random Forest, KNN
│       ├── modelo_prioridad.joblib
│       ├── dataset/
│       └── reportes/             # PNGs de comparación de modelos
└── CONTRIBUTING.md
```

---

## Instalación rápida

Consultá [`docs/setup.md`](docs/setup.md) para instrucciones detalladas.

```bash
# 1. Clonar el repositorio
git clone https://github.com/virginiaSchmied/LogiTrack.git
cd logitrack

# 2. Instalar dependencias del backend
cd src/backend
pip install -r requirements.txt

# 3. Aplicar migraciones
psql -U <usuario> -d <base> -f src/db/migrations/create_tabla_usuario.sql
# (ver setup.md para el orden completo)

# 4. Levantar el servidor
uvicorn main:app --reload
```

---

## Ejecutar tests

```bash
# Tests unitarios
cd src/backend
pytest

# Tests E2E
cd tests/e2e
pytest
```

---

## Contribuciones

Consultá [`CONTRIBUTING.md`](CONTRIBUTING.md) para conocer el flujo de trabajo y las convenciones del proyecto.

