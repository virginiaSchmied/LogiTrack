# Arquitectura — LogiTrack SFGLD

Este documento describe las decisiones de diseño y arquitectura del sistema LogiTrack en su versión de Paquete Base (TP Inicial).

---

## Visión general

LogiTrack sigue una arquitectura de **tres capas desacopladas**:

```
┌─────────────────────────────────────────┐
│            Frontend (SPA Vanilla JS)    │
│         index.html · app.js · style.css │
└────────────────────┬────────────────────┘
                     │ HTTP / REST (JSON)
┌────────────────────▼────────────────────┐
│          Backend (FastAPI / Python)     │
│   main.py · routers · models · schemas  │
└────────────────────┬────────────────────┘
                     │ SQLAlchemy / psycopg2
┌────────────────────▼────────────────────┐
│          Base de datos (PostgreSQL)     │
│        Migraciones SQL versionadas      │
└─────────────────────────────────────────┘
```

---

## Backend

### Framework: FastAPI

Se eligió FastAPI por su alto rendimiento, tipado estático con Pydantic y generación automática de documentación interactiva (Swagger UI en `/docs`, ReDoc en `/redoc`).

### Capas internas del backend

| Módulo | Responsabilidad |
|---|---|
| `main.py` | Punto de entrada, registro de routers, configuración de CORS |
| `database.py` | Conexión y sesión SQLAlchemy |
| `models.py` | Modelos ORM (tablas mapeadas a clases Python) |
| `schemas.py` | Esquemas Pydantic para validación de entrada/salida |
| `routers/envios.py` | Endpoints REST del recurso Envíos |

### Recurso principal: Envíos

El recurso `envios` expone las operaciones:

- `POST /envios` — Crear envío
- `GET /envios` — Listar envíos
- `GET /envios/{id}` — Detalle de un envío

---

## Base de datos

### Motor: PostgreSQL

Las migraciones se encuentran en `scr/db/migrations/` y deben ejecutarse en el siguiente orden:

1. `create_enums.sql` — Tipos enumerados (estados, roles, etc.)
2. `create_tabla_usuario.sql` — Tabla de usuarios
3. `create_tablas_rol_direccion.sql` — Roles y direcciones
4. `create_tabla_envio.sql` — Tabla principal de envíos
5. `create_tablas_eventos.sql` — Auditoría / eventos del sistema
6. `create_indices.sql` — Índices de performance
7. `insert_datos_iniciales.sql` — Datos semilla

---

## Frontend

Interfaz web liviana desarrollada con tecnologías nativas del navegador (sin frameworks). Se comunica con el backend mediante `fetch` sobre la API REST.

| Archivo | Rol |
|---|---|
| `index.html` | Estructura HTML principal |
| `app.js` | Lógica de interacción y llamadas a la API |
| `style.css` | Estilos globales |

---

## Testing

### Tests unitarios (pytest)

Ubicados en `scr/backend/tests/`. Cubren los endpoints principales del backend con una base de datos de prueba configurada en `conftest.py`.

### Tests E2E (Playwright)

Ubicados en `tests/e2e/`. Simulan flujos reales de usuario sobre el frontend:

| Archivo | Escenario cubierto |
|---|---|
| `test_formulario.py` | Flujo de creación de envío vía formulario |
| `test_accesibilidad.py` | Verificaciones de accesibilidad básica |

---

## Decisiones de diseño destacadas

- **Separación clara de capas**: frontend, backend y base de datos son independientes y pueden desplegarse por separado.
- **Migraciones versionadas**: se evita la generación automática de tablas para mantener control explícito del esquema.
- **Schemas Pydantic**: toda entrada y salida de la API está tipada y validada, reduciendo errores en runtime.
- **Paquete Base reutilizable**: la estructura está pensada para ser extendida con nuevos módulos (transportistas, rutas, reportes) sin modificar el núcleo existente.
