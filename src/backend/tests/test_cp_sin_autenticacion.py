"""
Tests de restricciones para usuarios no autenticados en operaciones de envíos.

Verifica que el backend bloquee el acceso a endpoints de creación, edición,
eliminación y cambio de estado de envíos cuando no existe sesión válida,
y que el endpoint de consulta pública no requiera autenticación.

User Stories cubiertas:
  LP-136 — Consultar envío por tracking ID (acceso público)
  LP-250 — Restringir acciones de modificación de envíos a usuarios no autenticados
  LP-252 — Restringir acciones de modificación de estado de envíos a usuarios no autenticados

Casos de Prueba:
  CP-0189  LP-136 CA-2  Consulta exitosa por tracking ID (Edge Case / sin token en endpoint privado)
  CP-0193  LP-136 CA-5  Acceso sin autenticación al endpoint público (Happy Path)
  CP-0284  LP-250 CA-1  Redirección al login al intentar registrar sin autenticación (Happy Path)
  CP-0285  LP-250 CA-2  Redirección al login al intentar editar sin autenticación (Happy Path)
  CP-0286  LP-250 CA-3  Redirección al login al intentar eliminar sin autenticación (Happy Path)
  CP-0288  LP-252 CA-1  Bloqueo de cambio de estado en flujo normal sin autenticación (Unhappy Path)
  CP-0289  LP-252 CA-2  Bloqueo de cambio a estados de excepción sin autenticación (Unhappy Path)
  CP-0291  LP-252 CA-5  Restricciones aplicadas en frontend y backend (Happy Path)

Nota sobre CP-0189:
  La US LP-136 incluye tanto el endpoint privado /envios/{tracking_id} (requiere auth)
  como el público /envios/publico/{tracking_id} (sin auth). CP-0189 (CA-2 Edge Case)
  verifica que el endpoint privado de búsqueda por tracking ID retorne 401 sin token,
  garantizando que la consulta detallada quede protegida. CP-0193 verifica el endpoint
  público (CA-5).
"""

# ── CP-0189: Sin token en endpoint privado de tracking → 401 ─────────────────

def test_cp0189_sin_token_endpoint_privado_tracking_retorna_401(client):
    """
    CP-0189 — LP-136 CA-2 — Edge Case.
    Dato: Request HTTP sin header Authorization.
    Precondición: usuario no autenticado.
    Acción: realiza la búsqueda en el endpoint autenticado de envíos.
    Resultado esperado: 401 Unauthorized.
    """
    resp = client.get("/envios/LT-00000001")
    assert resp.status_code == 401


def test_cp0189_sin_token_listar_envios_retorna_401(client):
    """
    CP-0189 — LP-136 CA-2 — Edge Case (listado).
    Sin token en GET /envios/ → 401 Unauthorized.
    """
    resp = client.get("/envios/")
    assert resp.status_code == 401


# ── CP-0193: Endpoint público no requiere autenticación ──────────────────────

def test_cp0193_endpoint_publico_no_requiere_autenticacion(client):
    """
    CP-0193 — LP-136 CA-5 — Happy Path.
    Dato: sesión sin token activo (usuario no logueado) con pantalla pública cargada.
    Precondición: un usuario no autenticado accede a la pantalla de consulta pública.
    Acción: intenta realizar la consulta al endpoint público.
    Resultado esperado: el sistema permite la operación sin requerir login (no retorna 401).
    El tracking ID no existe en la BD de test, por lo que se espera 404 (no 401 ni 403).
    """
    resp = client.get("/envios/publico/LT-99999999")
    assert resp.status_code != 401
    assert resp.status_code != 403


def test_cp0193_endpoint_publico_existente_retorna_200(client, headers_operador):
    """
    CP-0193 — LP-136 CA-5 — Happy Path (con envío existente).
    Crear un envío autenticado y luego consultarlo sin token → 200 OK.
    """
    from datetime import date, timedelta

    fecha_futura = str(date.today() + timedelta(days=30))
    payload = {
        "remitente": "Remitente Publico",
        "destinatario": "Destinatario Publico",
        "probabilidad_retraso": 0.1,
        "fecha_entrega_estimada": fecha_futura,
        "direccion_origen": {
            "calle": "Av San Martin", "numero": "100",
            "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000",
        },
        "direccion_destino": {
            "calle": "Belgrano", "numero": "200",
            "ciudad": "Cordoba", "provincia": "Cordoba", "codigo_postal": "5000",
        },
    }
    r = client.post("/envios/", json=payload, headers=headers_operador)
    assert r.status_code == 201
    tracking_id = r.json()["tracking_id"]

    # Consultar sin token → no debe retornar 401 ni 403
    resp_publico = client.get(f"/envios/publico/{tracking_id}")
    assert resp_publico.status_code == 200


# ── CP-0284: Sin autenticación, intentar registrar envío → 401 ───────────────

def test_cp0284_sin_token_registrar_envio_retorna_401(client):
    """
    CP-0284 — LP-250 CA-1 — Happy Path.
    Dato: sesión sin token activo (usuario no logueado) accediendo a URL del formulario.
    Precondición: usuario no autenticado intenta acceder al formulario de registro de envío.
    Acción: solicita la URL o la opción de registro.
    Resultado esperado: el sistema deniega el acceso y redirige al login (401 Unauthorized).
    """
    from datetime import date, timedelta

    fecha_futura = str(date.today() + timedelta(days=30))
    payload = {
        "remitente": "Juan Pérez",
        "destinatario": "María García",
        "probabilidad_retraso": 0.5,
        "fecha_entrega_estimada": fecha_futura,
        "direccion_origen": {
            "calle": "Av. Corrientes", "numero": "1234",
            "ciudad": "Buenos Aires", "provincia": "Buenos Aires", "codigo_postal": "1043",
        },
        "direccion_destino": {
            "calle": "San Martín", "numero": "567",
            "ciudad": "Córdoba", "provincia": "Córdoba", "codigo_postal": "5000",
        },
    }
    resp = client.post("/envios/", json=payload)
    assert resp.status_code == 401


def test_cp0284_sin_token_payload_vacio_tambien_retorna_401(client):
    """
    CP-0284 — LP-250 CA-1 — Variante.
    Sin token y payload vacío → la denegación ocurre antes de validar el cuerpo (401).
    """
    assert client.post("/envios/", json={}).status_code == 401


# ── CP-0285: Sin autenticación, intentar editar envío → 401 ──────────────────

def test_cp0285_sin_token_editar_datos_contacto_retorna_401(client):
    """
    CP-0285 — LP-250 CA-2 — Happy Path.
    Dato: sesión sin token activo accediendo a URL de edición de envío.
    Precondición: usuario no autenticado intenta acceder a la edición de un envío.
    Acción: solicita la URL o la acción de edición (datos de contacto).
    Resultado esperado: el sistema deniega el acceso y redirige al login (401 Unauthorized).
    """
    payload = {
        "destinatario": "Nuevo Destinatario",
        "direccion_destino": {
            "calle": "Mitre", "numero": "100",
            "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000",
        },
    }
    resp = client.patch("/envios/LT-00000001/contacto", json=payload)
    assert resp.status_code == 401


def test_cp0285_sin_token_editar_datos_operativos_retorna_401(client):
    """
    CP-0285 — LP-250 CA-2 — Variante (datos operativos).
    Sin token en PATCH /envios/{id}/operativo → 401 Unauthorized.
    """
    from datetime import date, timedelta

    payload = {
        "fecha_entrega_estimada": str(date.today() + timedelta(days=10)),
        "probabilidad_retraso": 0.3,
    }
    resp = client.patch("/envios/LT-00000001/operativo", json=payload)
    assert resp.status_code == 401


# ── CP-0286: Sin autenticación, intentar eliminar envío → 401 ────────────────

def test_cp0286_sin_token_eliminar_envio_retorna_401(client):
    """
    CP-0286 — LP-250 CA-3 — Happy Path.
    Dato: sesión sin token activo accediendo a URL de eliminación de envío.
    Precondición: usuario no autenticado intenta acceder a la acción de eliminar un envío.
    Acción: solicita la URL o la acción de eliminación.
    Resultado esperado: el sistema deniega el acceso y redirige al login (401 Unauthorized).
    """
    resp = client.delete("/envios/LT-00000001")
    assert resp.status_code == 401


def test_cp0286_sin_token_eliminar_envio_inexistente_tambien_retorna_401(client):
    """
    CP-0286 — LP-250 CA-3 — Variante.
    Sin token en DELETE /envios/{id} para ID inexistente → 401 (antes de buscar el envío).
    """
    assert client.delete("/envios/LT-99999999").status_code == 401


# ── CP-0288: Sin autenticación, intentar cambiar estado → 401 ────────────────

def test_cp0288_sin_token_cambiar_estado_envio_retorna_401(client):
    """
    CP-0288 — LP-252 CA-1 — Unhappy Path.
    Dato: sesión sin token activo accediendo a URL de cambio de estado de envío.
    Precondición: usuario no autenticado intenta acceder a la pantalla de cambio de estado.
    Acción: solicita la URL o la acción de cambio de estado.
    Resultado esperado: el sistema deniega el acceso y redirige al login (401 Unauthorized).
    """
    payload = {
        "nuevo_estado": "EN_DEPOSITO",
        "nueva_ubicacion": {
            "calle": "Mitre", "numero": "100",
            "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000",
        },
    }
    resp = client.patch("/envios/LT-00000001/estado", json=payload)
    assert resp.status_code == 401


def test_cp0288_sin_token_avanzar_estado_flujo_normal_retorna_401(client):
    """
    CP-0288 — LP-252 CA-1 — Variante (estado EN_TRANSITO).
    Sin token → intento de avanzar estado en flujo normal → 401.
    """
    payload = {"nuevo_estado": "EN_TRANSITO", "reusar_ubicacion_anterior": True}
    assert client.patch("/envios/LT-00000001/estado", json=payload).status_code == 401


# ── CP-0289: Sin autenticación, intentar aplicar estado de excepción → 401 ───

def test_cp0289_sin_token_aplicar_estado_retrasado_retorna_401(client):
    """
    CP-0289 — LP-252 CA-2 — Unhappy Path.
    Dato: sesión sin token accediendo a URL de cambio de estado de envío.
    Precondición: usuario no autenticado intenta aplicar un estado de excepción (Retrasado).
    Acción: solicita la URL o la acción de cambio de estado.
    Resultado esperado: el sistema deniega el acceso y redirige al login (401 Unauthorized).
    """
    payload = {
        "nuevo_estado": "RETRASADO",
        "nueva_ubicacion": {
            "calle": "Ruta 9", "numero": "200",
            "ciudad": "Mendoza", "provincia": "Mendoza", "codigo_postal": "5500",
        },
    }
    resp = client.patch("/envios/LT-00000001/estado", json=payload)
    assert resp.status_code == 401


def test_cp0289_sin_token_aplicar_estado_cancelado_retorna_401(client):
    """
    CP-0289 — LP-252 CA-2 — Variante (estado CANCELADO).
    Sin token → intento de aplicar estado de excepción CANCELADO → 401.
    """
    payload = {"nuevo_estado": "CANCELADO"}
    assert client.patch("/envios/LT-00000001/estado", json=payload).status_code == 401


def test_cp0289_sin_token_aplicar_estado_bloqueado_retorna_401(client):
    """
    CP-0289 — LP-252 CA-2 — Variante (estado BLOQUEADO).
    Sin token → intento de aplicar estado de excepción BLOQUEADO → 401.
    """
    payload = {
        "nuevo_estado": "BLOQUEADO",
        "nueva_ubicacion": {
            "calle": "Av. Italia", "numero": "500",
            "ciudad": "Tucuman", "provincia": "Tucuman", "codigo_postal": "4000",
        },
    }
    assert client.patch("/envios/LT-00000001/estado", json=payload).status_code == 401


# ── CP-0291: Sin autenticación, pantalla de envíos inaccessible ───────────────

def test_cp0291_sin_token_listar_envios_retorna_401(client):
    """
    CP-0291 — LP-252 CA-5 — Happy Path.
    Dato: sesión sin token activo (usuario no logueado) accediendo a pantalla de envíos.
    Precondición: usuario no autenticado accede a la interfaz del sistema.
    Acción: visualiza las pantallas de envíos (GET /envios/).
    Resultado esperado: las opciones no son visibles ni accesibles.
    Backend: retorna 401 Unauthorized → el frontend no puede mostrar las opciones.
    """
    resp = client.get("/envios/")
    assert resp.status_code == 401


def test_cp0291_sin_token_historial_envio_retorna_401(client):
    """
    CP-0291 — LP-252 CA-5 — Complementario (historial de estados).
    Sin token → GET /envios/{id}/historial → 401 (opciones de historial inaccesibles).
    """
    assert client.get("/envios/LT-00000001/historial").status_code == 401


def test_cp0291_sin_token_cambio_de_estado_es_bloqueado(client):
    """
    CP-0291 — LP-252 CA-5 — Complementario (cambio de estado).
    Sin token → PATCH /envios/{id}/estado → 401 (opción de cambio de estado inaccesible).
    """
    payload = {"nuevo_estado": "EN_DEPOSITO", "reusar_ubicacion_anterior": True}
    assert client.patch("/envios/LT-00000001/estado", json=payload).status_code == 401
