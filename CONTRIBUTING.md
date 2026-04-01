# Guía de Contribución — LogiTrack SFGLD

Este documento describe el flujo de trabajo, convenciones y requisitos para realizar aportes al proyecto.

---

## Requisitos previos

- Python 3.11+
- PostgreSQL 14+
- Node.js (solo para Playwright)
- Git

---

## Configuración del entorno de desarrollo

```bash
# Clonar el repositorio
git clone https://github.com/virginiaSchmied/LogiTrack.git
cd logitrack

# Crear entorno virtual
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# Instalar dependencias
cd src/backend
pip install -r requirements.txt
pip install -r requirements-test.txt
```

---

## Flujo de trabajo con Git


```
main
 └── develop
      ├── develop-<name> --> Rama individual para cada integrante
```

### Pasos para contribuir

1. **Crear una rama** desde `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b develop-<name>
   ```

2. **Desarrollar** los cambios con commits atómicos y descriptivos.

3. **Ejecutar los tests** antes de hacer push:
   ```bash
   cd src/backend
   pytest
   ```

4. **Hacer push** y abrir un Pull Request hacia `develop`:
   ```bash
   git push origin develop-<name>
   ```

5. El PR debe ser revisado y aprobado por al menos **un integrante del equipo** antes de hacer merge.

---

## Convenciones de commits

Se utiliza el estándar **Conventional Commits**:

```
<tipo>(<alcance>): <descripción breve>
```

| Tipo | Cuándo usarlo |
|---|---|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Cambios en documentación |
| `test` | Agregar o modificar tests |
| `refactor` | Refactorización sin cambio funcional |
| `chore` | Tareas de mantenimiento (deps, config) |

**Ejemplos:**
```
feat(envios): agregar endpoint de listado con paginación
fix(database): corregir string de conexión en conftest
docs(architecture): actualizar diagrama de capas
test(e2e): agregar test de accesibilidad en formulario
```

---

## Estructura de tests

### Tests unitarios

- Ubicación: src/backend/tests/`
- Framework: `pytest`
- Cada nuevo endpoint debe tener su archivo de test correspondiente (`test_<recurso>.py`)
- Usar fixtures definidas en `conftest.py` para la base de datos de prueba

```bash
cd src/backend
pytest --html=tests/reporte.html
```

### Tests E2E

- Ubicación: `tests/e2e/`
- Framework: Playwright
- Correr con el servidor backend activo

```bash
cd tests/e2e
pytest
```

---

## Migraciones de base de datos

- Todo cambio de esquema debe hacerse mediante un nuevo archivo `.sql` en `src/db/migrations/`
- Nombrar con prefijo descriptivo: `alter_tabla_envio_add_column_peso.sql`
- No modificar migraciones ya ejecutadas en entornos compartidos

---

## Estilo de código

- Seguir **PEP 8** para código Python
- Usar nombres en **español** para variables de dominio (envio, usuario, direccion) y en **inglés** para infraestructura (router, session, response)
- Todo endpoint nuevo debe incluir docstring y tipado completo

---

## Reportar issues

Abrir un issue en el repositorio con:
- Descripción clara del problema o sugerencia
- Pasos para reproducir (si es un bug)
- Comportamiento esperado vs. actual
