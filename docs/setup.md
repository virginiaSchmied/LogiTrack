# Guía de Instalación — LogiTrack SFGLD

Esta guía detalla los pasos para configurar el entorno de desarrollo local de LogiTrack.

---

## Requisitos del sistema

| Herramienta | Versión mínima |
|---|---|
| Python | 3.11 |
| PostgreSQL | 14 |
| pip | 23+ |
| Git | 2.x |
| Playwright (E2E) | última estable |

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/virginiaSchmied/LogiTrack.git
cd logitrack
```

---

## 2. Configurar el entorno virtual Python

```bash
python -m venv venv

# Activar (Linux/macOS)
source venv/bin/activate

# Activar (Windows PowerShell)
venv\Scripts\activate
```

---

## 3. Instalar dependencias del backend

```bash
cd src/backend
pip install -r requirements.txt
```

Para ejecutar tests también instalar:

```bash
pip install -r requirements-test.txt
```

---

## 4. Configurar la base de datos PostgreSQL

### 4.1 Crear la base de datos

```sql
CREATE DATABASE logitrack;
CREATE USER logitrack_user WITH PASSWORD 'tu_password';
GRANT ALL PRIVILEGES ON DATABASE logitrack TO logitrack_user;
```

### 4.2 Aplicar migraciones

Ejecutar los scripts en el siguiente orden desde `src/db/migrations/`:

```bash
psql -U logitrack_user -d logitrack -f src/db/migrations/create_enums.sql
psql -U logitrack_user -d logitrack -f src/db/migrations/create_tabla_usuario.sql
psql -U logitrack_user -d logitrack -f src/db/migrations/create_tablas_rol_direccion.sql
psql -U logitrack_user -d logitrack -f src/db/migrations/create_tabla_envio.sql
psql -U logitrack_user -d logitrack -f src/db/migrations/create_tablas_eventos.sql
psql -U logitrack_user -d logitrack -f src/db/migrations/create_indices.sql
psql -U logitrack_user -d logitrack -f src/db/migrations/insert_datos_iniciales.sql
```

---

## 5. Variables de entorno

Crear un archivo `.env` en `src/backend/` con el siguiente contenido:

```env
DATABASE_URL=postgresql://logitrack_user:tu_password@localhost:5432/logitrack
```

> El archivo `.env` está incluido en `.gitignore` y no debe subirse al repositorio.

---

## 6. Levantar el servidor backend

```bash
cd src/backend
uvicorn main:app --reload
```

El servidor quedará disponible en:
- API: [http://localhost:8000](http://localhost:8000)
- Documentación interactiva: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 7. Abrir el frontend

Abrir directamente en el navegador:

```
src/frontend/index.html
```

O servir con un servidor estático simple:

```bash
cd src/frontend
python -m http.server 3000
# Acceder en http://localhost:3000
```

---

## 8. Ejecutar los tests

### Tests unitarios (pytest)

```bash
cd src/backend
pytest

# Con reporte HTML
pytest --html=tests/reporte.html --self-contained-html
```

### Tests E2E (Playwright)

```bash
# Instalar browsers de Playwright (primera vez)
playwright install

cd tests/e2e
pytest
```

> Los tests E2E requieren que el servidor backend esté corriendo.

---

## Solución de problemas frecuentes

**Error de conexión a la base de datos**
Verificar que PostgreSQL esté corriendo y que `DATABASE_URL` en `.env` sea correcta.

**`ModuleNotFoundError` al correr pytest**
Asegurarse de estar con el entorno virtual activado y haber instalado `requirements-test.txt`.

**Puerto 8000 en uso**
```bash
uvicorn main:app --reload --port 8001
```
