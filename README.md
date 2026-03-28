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
| Tests unitarios | pytest |
| Tests E2E | Playwright |
| Control de versiones | Git / GitHub |

---

## Estructura del proyecto

```
LogiTrack/
├── docs/
│   ├── architecture.md       # Decisiones de arquitectura
│   └── setup.md              # Guía de instalación
├── scr/
│   ├── backend/              # API FastAPI
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── database.py
│   │   ├── routers/
│   │   │   └── envios.py
│   │   └── tests/            # Tests unitarios
│   ├── db/
│   │   └── migrations/       # Scripts SQL de migración
│   └── frontend/             # Interfaz web
│       ├── index.html
│       ├── app.js
│       └── style.css
└── tests/
    └── e2e/                  # Tests end-to-end con Playwright
```

---

## Instalación rápida

Consultá [`docs/setup.md`](docs/setup.md) para instrucciones detalladas.

```bash
# 1. Clonar el repositorio
git clone https://github.com/virginiaSchmied/LogiTrack.git
cd logitrack

# 2. Instalar dependencias del backend
cd scr/backend
pip install -r requirements.txt

# 3. Aplicar migraciones
psql -U <usuario> -d <base> -f scr/db/migrations/create_tabla_usuario.sql
# (ver setup.md para el orden completo)

# 4. Levantar el servidor
uvicorn main:app --reload
```

---

## Ejecutar tests

```bash
# Tests unitarios
cd scr/backend
pytest

# Tests E2E
cd tests/e2e
pytest
```

---

## Contribuciones

Consultá [`CONTRIBUTING.md`](CONTRIBUTING.md) para conocer el flujo de trabajo y las convenciones del proyecto.

