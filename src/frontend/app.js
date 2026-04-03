'use strict';

// ─── Config ───────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000"; 
//"http://18.191.173.105:8000";

// ─── Estado de autenticación ──────────────────────────────────────────────────
let _token    = null;
let _userEmail = null;
let _userRole  = null;   // "OPERADOR" | "SUPERVISOR" | "ADMINISTRADOR"

const LS_TOKEN = "lt_token";
const LS_EMAIL = "lt_email";
const LS_ROLE  = "lt_role";

function loadAuthState() {
  _token     = localStorage.getItem(LS_TOKEN) || null;
  _userEmail = localStorage.getItem(LS_EMAIL) || null;
  _userRole  = localStorage.getItem(LS_ROLE)  || null;
}

function saveAuthState(token, email, role) {
  _token     = token;
  _userEmail = email;
  _userRole  = role;
  localStorage.setItem(LS_TOKEN, token);
  localStorage.setItem(LS_EMAIL, email);
  localStorage.setItem(LS_ROLE,  role);
}

function clearAuthState() {
  _token = _userEmail = _userRole = null;
  localStorage.removeItem(LS_TOKEN);
  localStorage.removeItem(LS_EMAIL);
  localStorage.removeItem(LS_ROLE);
}

function isAuthenticated() {
  return !!_token;
}

function authHeaders() {
  return _token ? { "Authorization": `Bearer ${_token}` } : {};
}

// ─── Mapa de badges por estado ────────────────────────────────────────────────
const BADGE_CLASS = {
  'REGISTRADO':      'badge-registrado',
  'EN_TRANSITO':     'badge-transito',
  'EN_SUCURSAL':     'badge-sucursal',
  'EN_DISTRIBUCION': 'badge-distribucion',
  'ENTREGADO':       'badge-entregado',
  'RETRASADO':       'badge-retrasado',
  'CANCELADO':       'badge-cancelado',
  'BLOQUEADO':       'badge-bloqueado',
  'ELIMINADO':       'badge-eliminado',
};

const BADGE_LABEL = {
  'REGISTRADO':      'Registrado',
  'EN_TRANSITO':     'En tránsito',
  'EN_SUCURSAL':     'En sucursal',
  'EN_DISTRIBUCION': 'En distribución',
  'ENTREGADO':       'Entregado',
  'RETRASADO':       'Retrasado',
  'CANCELADO':       'Cancelado',
  'BLOQUEADO':       'Bloqueado',
  'ELIMINADO':       'Eliminado',
};

// ─── Mapa de badges por prioridad ────────────────────────────────────────────
const PRIORIDAD_BADGE_CLASS = {
  'ALTA':  'badge-prioridad-alta',
  'MEDIA': 'badge-prioridad-media',
  'BAJA':  'badge-prioridad-baja',
};

const PRIORIDAD_BADGE_LABEL = {
  'ALTA':  'Alta',
  'MEDIA': 'Media',
  'BAJA':  'Baja',
};

function prioridadBadge(prioridad) {
  if (!prioridad) return `<span class="badge badge-prioridad-null">Sin clasificar</span>`;
  const cls   = PRIORIDAD_BADGE_CLASS[prioridad] || 'badge-prioridad-null';
  const label = PRIORIDAD_BADGE_LABEL[prioridad] || prioridad;
  return `<span class="badge ${cls}">${escHtml(label)}</span>`;
}

// ─── Init de la aplicación ────────────────────────────────────────────────────
function initApp() {
  loadAuthState();
  if (isAuthenticated()) {
    showApp();
  } else {
    showLoginScreen();
  }
}

function showLoginScreen() {
  document.getElementById('login-screen').style.display = '';
  document.getElementById('app-wrapper').style.display  = 'none';
  closeLoginModal();
}

function openLoginModal() {
  document.getElementById('login-modal').style.display = '';
  document.getElementById('login-email').value    = '';
  document.getElementById('login-password').value = '';
  _hideLoginError();
  _clearLoginFieldError('login-email');
  _clearLoginFieldError('login-password');
  setTimeout(() => document.getElementById('login-email').focus(), 50);
} 

function closeLoginModal() {
  document.getElementById('login-modal').style.display = 'none';
}

function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app-wrapper').style.display  = '';
  applyRoleUI();
}

// ─── Aplicar la UI según el rol ───────────────────────────────────────────────
// LP-102: la interfaz muestra u oculta opciones según el rol del usuario.
function applyRoleUI() {
  const role = _userRole;

  // Actualizar el badge de usuario en el navbar
  const badgeText = document.getElementById('user-badge-text');
  if (badgeText) {
    const roleLabel = { OPERADOR: 'Operador', SUPERVISOR: 'Supervisor', ADMINISTRADOR: 'Administrador' }[role] || role;
    badgeText.textContent = `${roleLabel} · ${_userEmail || ''}`;
  }

  const navTabsEnvios = document.getElementById('nav-tabs-envios');
  const viewList      = document.getElementById('view-list');
  const viewForm      = document.getElementById('view-form');
  const viewAdmin     = document.getElementById('view-admin');
  const btnNuevoEnvio = document.getElementById('btn-nuevo-envio');

  if (role === 'ADMINISTRADOR') {
    // LP-102 CA-3: Admin solo ve gestión de usuarios
    if (navTabsEnvios) navTabsEnvios.style.display = 'none';
    if (viewAdmin) { viewAdmin.style.display = ''; viewAdmin.classList.add('active'); }
    if (viewList)  viewList.style.display  = 'none';
    if (viewForm)  viewForm.style.display  = 'none';
  } else {
    // OPERADOR o SUPERVISOR: muestran envíos
    if (navTabsEnvios) navTabsEnvios.style.display = '';
    if (viewAdmin) viewAdmin.style.display = 'none';

    // El botón "Nuevo envío" es visible para ambos (LP-102 CA-1 y CA-2)
    if (btnNuevoEnvio) btnNuevoEnvio.style.display = '';

    // Mostrar la vista de listado como activa por defecto
    showView('list');
  }
}

// ─── Redirigir a login ante error 401 ────────────────────────────────────────
// LP-21 CA-7 / LP-250 CA-1
async function handleApiError(res) {
  if (res.status === 401) {
    clearAuthState();
    showLoginScreen();
    openLoginModal();
    return true; // fue un 401
  }
  return false;
}

// ─── Login ────────────────────────────────────────────────────────────────────
async function submitLogin() {
  const emailEl = document.getElementById('login-email');
  const passEl  = document.getElementById('login-password');
  const btn     = document.getElementById('btn-login');

  // Validar campos vacíos (LP-21 CA-4)
  let valid = true;
  if (!emailEl.value.trim()) {
    _setLoginFieldError('login-email', 'Ingresá tu email.');
    valid = false;
  } else {
    _clearLoginFieldError('login-email');
  }
  if (!passEl.value) {
    _setLoginFieldError('login-password', 'Ingresá tu contraseña.');
    valid = false;
  } else {
    _clearLoginFieldError('login-password');
  }
  if (!valid) return;

  btn.disabled = true;
  btn.textContent = 'Ingresando…';
  _hideLoginError();

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: emailEl.value.trim(), password: passEl.value }),
    });

    if (!res.ok) {
      // LP-21 CA-3: mensaje genérico sin revelar qué campo es incorrecto
      _showLoginError('Email o contraseña incorrectos. Verificá tus datos e intentá de nuevo.');
      return;
    }

    const data = await res.json();
    saveAuthState(data.access_token, data.email, data.nombre_rol);
    showApp();

    closeLoginModal();


  } catch (err) {
    console.error('Error al iniciar sesión:', err);
    _showLoginError('No se pudo conectar con el servidor. Verificá que el sistema esté disponible.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Ingresar';
  }
}

function _showLoginError(msg) {
  const el = document.getElementById('login-error');
  el.textContent = msg;
  el.classList.add('visible');
}

function _hideLoginError() {
  const el = document.getElementById('login-error');
  el.classList.remove('visible');
  el.textContent = '';
}

function _setLoginFieldError(id, msg) {
  const input = document.getElementById(id);
  const error = document.getElementById('err-' + id);
  if (input) input.setAttribute('aria-invalid', 'true');
  if (error) { error.textContent = msg; error.classList.add('visible'); }
}

function _clearLoginFieldError(id) {
  const input = document.getElementById(id);
  const error = document.getElementById('err-' + id);
  if (input) input.setAttribute('aria-invalid', 'false');
  if (error) error.classList.remove('visible');
}

// ─── Logout ───────────────────────────────────────────────────────────────────
// LP-99: cierra sesión e invalida el token en el cliente.
async function logout() {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: authHeaders(),
    });
  } catch (err) {
    console.warn('Error al registrar logout en el servidor:', err);
    // El logout en el cliente procede aunque el servidor falle
  }
  clearAuthState();
  showLoginScreen();
}

// ─── Consulta pública por tracking ID (CA-2, CA-3, CA-4, CA-5) ──────────────
async function buscarPublico() {
  const input      = document.getElementById('public-track-input');
  const resultEl   = document.getElementById('public-track-result');
  const trackingId = input.value.trim().toUpperCase();

  if (!trackingId) {
    resultEl.style.display = 'block';
    resultEl.innerHTML = `<p class="track-error">Ingresá un tracking ID.</p>`;
    return;
  }

  resultEl.style.display = 'block';
  resultEl.innerHTML = `<p style="font-size:.82rem;color:var(--text-sub)">Consultando…</p>`;

  try {
    const res = await fetch(`${API_BASE}/envios/publico/${encodeURIComponent(trackingId)}`);
    if (res.status === 404) {
      resultEl.innerHTML = `<p class="track-error">No se encontró ningún envío con el tracking ID <strong>${escHtml(trackingId)}</strong>. Verificá el código e intentá nuevamente.</p>`;
      return;
    }
    if (!res.ok) throw new Error(`Error ${res.status}`);

    const e = await res.json();
    resultEl.innerHTML = `
      <div class="track-result-card">
        <div class="track-result-header">
          <span class="track-result-tid">${escHtml(e.tracking_id)}</span>
          <span class="badge ${BADGE_CLASS[e.estado] || 'badge-registrado'}">${escHtml(BADGE_LABEL[e.estado] || e.estado)}</span>
        </div>
        <div class="detail-grid" style="margin-top:.85rem">
          <div class="detail-section">
            <div class="section-title">Estado del envío</div>
            <dl class="detail-list">
              <div class="dl-row">
                <dt>Entrega estimada</dt>
                <dd class="mono-text">${escHtml(formatFecha(e.fecha_entrega_estimada))}</dd>
              </div>
            </dl>
          </div>
          <div class="detail-cols">
            <div class="detail-section">
              <div class="section-title">Origen</div>
              <dl class="detail-list">
                <div class="dl-row"><dt>Ciudad</dt><dd>${escHtml(e.ciudad_origen)}</dd></div>
                <div class="dl-row"><dt>Provincia</dt><dd>${escHtml(e.provincia_origen)}</dd></div>
              </dl>
            </div>
            <div class="detail-section">
              <div class="section-title">Destino</div>
              <dl class="detail-list">
                <div class="dl-row"><dt>Ciudad</dt><dd>${escHtml(e.ciudad_destino)}</dd></div>
                <div class="dl-row"><dt>Provincia</dt><dd>${escHtml(e.provincia_destino)}</dd></div>
              </dl>
            </div>
          </div>
        </div>
      </div>`;
  } catch (err) {
    console.error('Error en consulta pública:', err);
    resultEl.innerHTML = `<p class="track-error">No se pudo conectar con el servidor.</p>`;
  }
}


function limpiarBusqueda() {
  document.getElementById('public-track-input').value = '';
  const resultEl = document.getElementById('public-track-result');
  resultEl.style.display = 'none';
  resultEl.innerHTML = '';
}

// ─── Navegación ───────────────────────────────────────────────────────────────
function showView(viewName) {
  // Ocultar todas las vistas
  document.querySelectorAll('.view').forEach(v => {
    v.style.display = 'none';
    v.classList.remove('active');
  });
  document.querySelectorAll('.nav-tabs button').forEach(b => {
    b.classList.remove('active');
    b.removeAttribute('aria-current');
  });

  const view = document.getElementById('view-' + viewName);
  if (view) {
    view.style.display = '';
    view.classList.add('active');
  }
  const tab = document.getElementById('tab-' + viewName);
  if (tab) {
    tab.classList.add('active');
    tab.setAttribute('aria-current', 'page');
  }

  if (viewName === 'form') resetForm();
  if (viewName === 'list') {
    document.getElementById('search-input').value = '';
    cargarEnvios('', 1);
  }
}

// ─── Paginación ───────────────────────────────────────────────────────────────
const PAGE_SIZE   = 20;
let currentPage   = 1;
let currentQuery  = '';
let totalEnvios   = 0;

function renderPaginacion(total, page) {
  const pag        = document.getElementById('paginacion');
  const totalPages = Math.ceil(total / PAGE_SIZE);
  if (totalPages <= 1) { pag.style.display = 'none'; return; }
  pag.style.display = 'flex';
  document.getElementById('pag-info').textContent         = `Página ${page} de ${totalPages}`;
  document.getElementById('btn-anterior').disabled        = page <= 1;
  document.getElementById('btn-siguiente').disabled       = page >= totalPages;
}

function paginaAnterior() {
  if (currentPage > 1) cargarEnvios(currentQuery, currentPage - 1);
}

function paginaSiguiente() {
  if (currentPage < Math.ceil(totalEnvios / PAGE_SIZE)) cargarEnvios(currentQuery, currentPage + 1);
}

// ─── Carga de envíos desde la API ─────────────────────────────────────────────
async function cargarEnvios(q = '', page = 1) {
  currentQuery = q;
  currentPage  = page;

  const tbody = document.getElementById('table-body');
  const table = document.getElementById('envios-table');
  const empty = document.getElementById('empty-state');
  const noRes = document.getElementById('no-results');
  const chip  = document.getElementById('count-chip');
  const pag   = document.getElementById('paginacion');

  try {
    const skip   = (page - 1) * PAGE_SIZE;
    const params = new URLSearchParams({ skip, limit: PAGE_SIZE });
    if (q.trim()) params.set('q', q.trim());
    const url = `${API_BASE}/envios?${params}`;

    const res = await fetch(url, { headers: authHeaders() });

    if (await handleApiError(res)) return; // 401 → ya redirigió a login
    if (!res.ok) throw new Error(`Error ${res.status}`);

    const data  = await res.json();
    const envios = data.items;
    totalEnvios  = data.total;

    chip.textContent = data.total;

    if (data.total === 0 && !q.trim()) {
      table.style.display = 'none';
      pag.style.display   = 'none';
      empty.style.display = '';
      noRes.style.display = 'none';
      empty.querySelector('.e-title').textContent = 'No hay envíos registrados';
      empty.querySelector('.e-desc').textContent  = 'Registrá el primer envío usando el botón de arriba.';
      return;
    }

    if (envios.length === 0) {
      table.style.display = 'none';
      pag.style.display   = 'none';
      empty.style.display = 'none';
      noRes.style.display = '';
      return;
    }

    empty.style.display = 'none';
    noRes.style.display = 'none';
    table.style.display = '';

    tbody.innerHTML = envios.map(e => `
      <tr class="row-clickable" onclick="openDetalle('${escHtml(e.tracking_id)}')" title="Ver detalle de ${escHtml(e.tracking_id)}">
        <td data-label="Tracking ID"><span class="tid-text">${escHtml(e.tracking_id)}</span></td>
        <td data-label="Remitente">${escHtml(e.remitente)}</td>
        <td data-label="Destinatario">${escHtml(e.destinatario)}</td>
        <td data-label="Ciudad Origen" class="sub-text">${escHtml(e.ciudad_origen)}, ${escHtml(e.provincia_origen)}</td>
        <td data-label="Ciudad Destino" class="sub-text">${escHtml(e.ciudad_destino)}, ${escHtml(e.provincia_destino)}</td>
        <td data-label="Estado"><span class="badge ${BADGE_CLASS[e.estado] || 'badge-registrado'}">${escHtml(BADGE_LABEL[e.estado] || e.estado)}</span></td>
        <td data-label="Prioridad">${prioridadBadge(e.prioridad)}</td>
        <td data-label="Entrega estimada" class="mono-text">${escHtml(formatFecha(e.fecha_entrega_estimada))}</td>
      </tr>
    `).join('');

    renderPaginacion(data.total, page);

  } catch (err) {
    console.error('Error al cargar envíos:', err);
    chip.textContent = '—';
    table.style.display = 'none';
    pag.style.display   = 'none';
    noRes.style.display = 'none';
    empty.style.display = '';
    empty.querySelector('.e-title').textContent = 'Error al conectar con el servidor';
    empty.querySelector('.e-desc').textContent  = 'Verificá que el backend esté corriendo e intentá de nuevo.';
  }
}

function formatFecha(iso) {
  if (!iso) return '-';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function formatDatetime(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString('es-AR') + ' · ' + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}


// ─── Grafo de transiciones de estado ─────────────────────────────────────────
const TRANSICIONES_VALIDAS = {
  'REGISTRADO':      ['EN_DEPOSITO', 'CANCELADO'],
  'EN_DEPOSITO':     ['EN_TRANSITO', 'RETRASADO', 'BLOQUEADO', 'CANCELADO'],
  'EN_TRANSITO':     ['EN_SUCURSAL', 'RETRASADO'],
  'EN_SUCURSAL':     ['EN_DISTRIBUCION', 'RETRASADO', 'BLOQUEADO', 'CANCELADO'],
  'EN_DISTRIBUCION': ['ENTREGADO', 'RETRASADO'],
  'ENTREGADO':       [],
  'RETRASADO':       ['EN_DEPOSITO', 'EN_TRANSITO', 'EN_SUCURSAL', 'EN_DISTRIBUCION'],
  'BLOQUEADO':       ['EN_DEPOSITO', 'EN_SUCURSAL'],
  'CANCELADO':       [],
  'ELIMINADO':       [],
};

const ESTADOS_EXCEPCION              = ['RETRASADO', 'CANCELADO', 'BLOQUEADO'];
const FLUJO_NORMAL                   = ['REGISTRADO', 'EN_DEPOSITO', 'EN_TRANSITO', 'EN_SUCURSAL', 'EN_DISTRIBUCION', 'ENTREGADO'];
const ESTADOS_UBICACION_OBLIGATORIA  = ['EN_DEPOSITO', 'EN_SUCURSAL', 'ENTREGADO'];


// ─── Modal de detalle ─────────────────────────────────────────────────────────
let _envioDetalle = null;

async function openDetalle(trackingId) {
  const overlay  = document.getElementById('modal-overlay');
  const body     = document.getElementById('modal-body');
  const tidEl    = document.getElementById('modal-tracking-id');
  const estadoEl = document.getElementById('modal-estado-badge');

  tidEl.textContent  = trackingId;
  estadoEl.innerHTML = '';
  body.innerHTML     = '<div class="modal-loading">Cargando detalle…</div>';
  document.getElementById('btn-eliminar').style.display = 'none';
  document.getElementById('btn-editar').style.display   = 'none';
  document.getElementById('btn-cambiar-estado').style.display = 'none';
  overlay.style.display = 'flex';
  document.body.style.overflow = 'hidden';

  try {
    // GET /{tracking_id} es público (LP-136), no requiere token
    const res = await fetch(`${API_BASE}/envios/${encodeURIComponent(trackingId)}`);
    if (!res.ok) throw new Error(`Error ${res.status}`);
    const e = await res.json();
    _envioDetalle = e;

    estadoEl.innerHTML = `<span class="badge ${BADGE_CLASS[e.estado] || 'badge-registrado'}">${escHtml(BADGE_LABEL[e.estado] || e.estado)}</span>`;

    // Botones de acción condicionados al rol (LP-102)
    const btnEliminar = document.getElementById('btn-eliminar');
    const btnEditar   = document.getElementById('btn-editar');
     const btnCambiarEstado = document.getElementById('btn-cambiar-estado');
     
     // Edit (contacto/operativo): show for non-ELIMINADO, non-CANCELADO
    if (e.estado !== 'ELIMINADO' && e.estado !== 'CANCELADO') {
      btnEditar.style.display = '';
      btnEditar.onclick = () => { closeDetalle(); openEdit(e.tracking_id, e); };
    }
    // Delete: only for CANCELADO and SUPERVISOR role (LP-102)
    if (e.estado === 'CANCELADO' && _userRole === 'SUPERVISOR') {
      btnEliminar.style.display = '';
      btnEliminar.onclick = () => openConfirmDelete(e.tracking_id, e.remitente, e.destinatario);
    }
    // Editar estado: only when transitions exist
    const transiciones = TRANSICIONES_VALIDAS[e.estado] || [];
    if (transiciones.length > 0) {
      btnCambiarEstado.style.display = '';
      btnCambiarEstado.onclick = () => { closeDetalle(); openEstado(e.tracking_id, e.estado, e.ultima_ubicacion || null, e.estado_revertir || null); };
    }

    body.innerHTML = `
      <div class="detail-grid">

        <div class="detail-section">
          <div class="section-title">Datos generales</div>
          <dl class="detail-list">
            <div class="dl-row"><dt>Remitente</dt><dd>${escHtml(e.remitente)}</dd></div>
            <div class="dl-row"><dt>Destinatario</dt><dd>${escHtml(e.destinatario)}</dd></div>
            <div class="dl-row"><dt>Prioridad</dt><dd>${prioridadBadge(e.prioridad)}</dd></div>
            <div class="dl-row"><dt>Entrega estimada</dt><dd class="mono-text">${escHtml(formatFecha(e.fecha_entrega_estimada))}</dd></div>
            <div class="dl-row"><dt>Registrado</dt><dd class="mono-text">${escHtml(formatDatetime(e.created_at))}</dd></div>
            <div class="dl-row"><dt>Última actualización</dt><dd class="mono-text">${escHtml(formatDatetime(e.updated_at))}</dd></div>
          </dl>
        </div>

        <div class="detail-cols">
          <div class="detail-section">
            <div class="section-title">Dirección de origen</div>
            <dl class="detail-list">
              <div class="dl-row"><dt>Calle</dt><dd>${escHtml(e.direccion_origen.calle)} ${escHtml(e.direccion_origen.numero)}</dd></div>
              <div class="dl-row"><dt>Ciudad</dt><dd>${escHtml(e.direccion_origen.ciudad)}</dd></div>
              <div class="dl-row"><dt>Provincia</dt><dd>${escHtml(e.direccion_origen.provincia)}</dd></div>
              <div class="dl-row"><dt>Cód. postal</dt><dd class="mono-text">${escHtml(e.direccion_origen.codigo_postal)}</dd></div>
            </dl>
          </div>
          <div class="detail-section">
            <div class="section-title">Dirección de destino</div>
            <dl class="detail-list">
              <div class="dl-row"><dt>Calle</dt><dd>${escHtml(e.direccion_destino.calle)} ${escHtml(e.direccion_destino.numero)}</dd></div>
              <div class="dl-row"><dt>Ciudad</dt><dd>${escHtml(e.direccion_destino.ciudad)}</dd></div>
              <div class="dl-row"><dt>Provincia</dt><dd>${escHtml(e.direccion_destino.provincia)}</dd></div>
              <div class="dl-row"><dt>Cód. postal</dt><dd class="mono-text">${escHtml(e.direccion_destino.codigo_postal)}</dd></div>
            </dl>
          </div>
        </div>

      </div>
    `;
  } catch (err) {
    console.error('Error al cargar detalle:', err);
    body.innerHTML = `
      <div class="empty-state">
        <div class="e-icon">⚠️</div>
        <div class="e-title">Error al cargar el detalle</div>
        <p class="e-desc">${escHtml(err.message)}</p>
      </div>`;
  }
}

function closeDetalle() {
  document.getElementById('modal-overlay').style.display = 'none';
  document.getElementById('btn-eliminar').style.display  = 'none';
  document.getElementById('btn-editar').style.display    = 'none';
  document.getElementById('btn-cambiar-estado').style.display  = 'none';
  document.body.style.overflow = '';
  _envioDetalle = null;
}



// ─── Eliminación de envío ─────────────────────────────────────────────────────
let _envioAEliminar = null;

function openConfirmDelete(trackingId, remitente, destinatario) {
  _envioAEliminar = trackingId;
  document.getElementById('confirm-tracking-id').textContent  = trackingId;
  document.getElementById('confirm-remitente').textContent    = remitente;
  document.getElementById('confirm-destinatario').textContent = destinatario;
  document.getElementById('confirm-overlay').style.display    = 'flex';
}

function closeConfirmDelete() {
  document.getElementById('confirm-overlay').style.display = 'none';
  _envioAEliminar = null;
}

async function confirmarEliminacion() {
  if (!_envioAEliminar) return;
  const trackingId = _envioAEliminar;
  closeConfirmDelete();
  closeDetalle();

  try {
    const res = await fetch(`${API_BASE}/envios/${encodeURIComponent(trackingId)}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (await handleApiError(res)) return;
    if (!res.ok) throw new Error(`Error ${res.status}`);
    showToast(trackingId, 'Envío eliminado correctamente');
    cargarEnvios(currentQuery, 1);
  } catch (err) {
    console.error('Error al eliminar envío:', err);
    alert('No se pudo eliminar el envío. Verificá que el backend esté corriendo.');
  }
}

// ─── Cambio de estado ─────────────────────────────────────────────────────────
let _trackingIdEnCambioEstado = null;
let _estadoActualEnCambio     = null;
let _ultimaUbicacion          = null;
let _estadoSeleccionado       = null;

function openEstado(trackingId, estadoActual, ultimaUbicacion = null, estadoRevertir = null) {
  _trackingIdEnCambioEstado = trackingId;
  _estadoActualEnCambio     = estadoActual;
  _ultimaUbicacion          = ultimaUbicacion;
  _estadoSeleccionado       = null;

  document.getElementById('estado-modal-tid').textContent = trackingId;

  // RETRASADO y BLOQUEADO solo pueden revertir al estado normal previo (no a cualquier válido del grafo)
  const ESTADOS_REVERSIBLES = ['RETRASADO', 'BLOQUEADO'];
  const esReversible = ESTADOS_REVERSIBLES.includes(estadoActual);
  const badgeActual  = `<span class="badge ${BADGE_CLASS[estadoActual] || ''}">${escHtml(BADGE_LABEL[estadoActual] || estadoActual)}</span>`;

  // Si es reversible y tenemos el estado previo, mostrar solo esa opción; si no, usar el grafo completo
  // OPERADOR no puede asignar excepciones (RETRASADO/BLOQUEADO): solo SUPERVISOR puede
  // OPERADOR no puede asignar excepciones ni cancelar: solo SUPERVISOR puede
  const ESTADOS_SOLO_SUPERVISOR = ['RETRASADO', 'BLOQUEADO', 'CANCELADO'];
  const transicionesBase = esReversible && estadoRevertir
    ? [estadoRevertir]
    : TRANSICIONES_VALIDAS[estadoActual] || [];
  const transiciones = _userRole !== 'SUPERVISOR'
    ? transicionesBase.filter(t => !ESTADOS_SOLO_SUPERVISOR.includes(t))
    : transicionesBase;

    
  let opcionesHtml = `
    <div class="estado-actual-row">
      <span class="form-label">Estado actual</span>
      ${badgeActual}
    </div>
    <div class="section-title">Seleccionar acción</div>
  `;

  transiciones.forEach(target => {
    const badgeTarget  = `<span class="badge ${BADGE_CLASS[target] || ''}">${escHtml(BADGE_LABEL[target] || target)}</span>`;
    const esExcTarget  = ESTADOS_EXCEPCION.includes(target);
    const esCancelar   = target === 'CANCELADO';
    const opcionLabel  = esReversible ? 'Revertir al flujo normal'
                       : esCancelar   ? 'Cancelar envío'
                       : esExcTarget  ? 'Asignar excepción'
                       :                'Avanzar en el flujo';
    const cardClass    = esCancelar ? 'estado-opcion-card cancelar-card' : 'estado-opcion-card';

    opcionesHtml += `
      <div class="${cardClass}" id="opcion-${target}" onclick="selectOpcion('${target}')">
        <div class="opcion-label">${escHtml(opcionLabel)}</div>
        <div class="estado-transicion-mini">
          ${badgeActual}
          <span class="estado-flecha">→</span>
          ${badgeTarget}
        </div>
      </div>`;
  });

  // Auto-select si hay una sola opción (incluyendo el caso de revertir)
  if (transiciones.length === 1) {
    _estadoSeleccionado = transiciones[0];
  }

  document.getElementById('estado-opciones-wrap').innerHTML = opcionesHtml;

  // Auto-add selected class if auto-selected
  if (_estadoSeleccionado) {
    document.getElementById(`opcion-${_estadoSeleccionado}`)?.classList.add('selected');
  }

  // Mostrar la última ubicación registrada (solo lectura)
  const displayUbicacion = document.getElementById('ultima-ubicacion-display');
  if (ultimaUbicacion) {
    displayUbicacion.style.display = '';
    displayUbicacion.innerHTML = `
      <div class="ubicacion-actual-box">
        <span class="ubicacion-actual-linea">${escHtml(ultimaUbicacion.calle)} ${escHtml(ultimaUbicacion.numero)}</span>
        <span class="ubicacion-actual-linea">${escHtml(ultimaUbicacion.ciudad)}, ${escHtml(ultimaUbicacion.provincia)} · CP ${escHtml(ultimaUbicacion.codigo_postal)}</span>
      </div>`;
  } else {
    displayUbicacion.style.display = '';
    displayUbicacion.innerHTML = `
      <div class="ubicacion-actual-box ubicacion-actual-vacia">
        <span class="ubicacion-actual-linea">Aún no se han registrado ubicaciones</span>
      </div>`;
  }

  _clearEstadoErrors();
  ['estado-calle', 'estado-numero', 'estado-cp', 'estado-ciudad', 'estado-provincia']
    .forEach(id => { document.getElementById(id).value = ''; });

  _aplicarUbicacionUI(_estadoSeleccionado, ultimaUbicacion, esReversible);

  document.getElementById('estado-overlay').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function selectOpcion(opcion) {
  _estadoSeleccionado = opcion;
  document.querySelectorAll('.estado-opcion-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`opcion-${opcion}`)?.classList.add('selected');
  // Es reversión si el estado actual es RETRASADO o BLOQUEADO (el target siempre es flujo normal)
  const esReversion = ['RETRASADO', 'BLOQUEADO'].includes(_estadoActualEnCambio);
  _aplicarUbicacionUI(opcion, _ultimaUbicacion, esReversion);
}

function _aplicarUbicacionUI(targetEstado, ultimaUbicacion, esReversion = false) {
  const titulo    = document.getElementById('ubicacion-section-title');
  const display   = document.getElementById('ultima-ubicacion-display');
  const reusarWrap = document.getElementById('reusar-wrap');
  const formFields = document.getElementById('ubicacion-form-fields');

  // Limpiar error general al cambiar de opción
  document.getElementById('err-ubicacion-general').classList.remove('visible');

  // CANCELADO: no requiere ubicación — ocultar toda la sección
  if (targetEstado === 'CANCELADO') {
    titulo.style.display    = 'none';
    display.style.display   = 'none';
    reusarWrap.style.display = 'none';
    formFields.style.display = 'none';
    document.getElementById('reusar-ubicacion').checked = false;
    return;
  }

  // Resto: mostrar sección
  titulo.style.display  = '';
  display.style.display = '';

  // EN_SUCURSAL / ENTREGADO: nueva dirección obligatoria
  if (targetEstado != null && ESTADOS_UBICACION_OBLIGATORIA.includes(targetEstado)) {
    reusarWrap.style.display = 'none';
    document.getElementById('reusar-ubicacion').checked = false;
    formFields.style.display = '';
    return;
  }

  // Resto (incluyendo reversiones): pre-marcar si hay ubicación previa
  reusarWrap.style.display = '';
  const preMarcar = esReversion || ultimaUbicacion != null;
  document.getElementById('reusar-ubicacion').checked = preMarcar;
  formFields.style.display = preMarcar ? 'none' : '';
}

function closeEstado() {
  document.getElementById('estado-overlay').style.display = 'none';
  document.body.style.overflow = '';
  _trackingIdEnCambioEstado = null;
  _estadoActualEnCambio     = null;
  _ultimaUbicacion          = null;
  _estadoSeleccionado       = null;
}

function toggleReusar(checked) {
  const formFields = document.getElementById('ubicacion-form-fields');
  if (checked) {
    formFields.style.display = 'none';
    _clearEstadoErrors();
    document.getElementById('err-ubicacion-general').classList.remove('visible');
  } else {
    formFields.style.display = '';
    ['estado-calle', 'estado-numero', 'estado-cp', 'estado-ciudad', 'estado-provincia']
      .forEach(id => { document.getElementById(id).value = ''; });
    _clearEstadoErrors();
  }
}

function _clearEstadoErrors() {
  ['estado-calle', 'estado-numero', 'estado-cp', 'estado-ciudad', 'estado-provincia'].forEach(id => {
    const input = document.getElementById(id);
    const error = document.getElementById('err-' + id);
    if (input) input.setAttribute('aria-invalid', 'false');
    if (error) error.classList.remove('visible');
  });
}

async function submitCambioEstado() {
  if (!_estadoSeleccionado) {
    alert('Seleccioná una acción antes de confirmar.');
    return;
  }

  // Confirmation for CANCELADO (irreversible)
  if (_estadoSeleccionado === 'CANCELADO') {
    openConfirmCancelar();
    return;
  }

  await _ejecutarCambioEstado();
}

async function _ejecutarCambioEstado() {
  const reusar = document.getElementById('reusar-ubicacion').checked;
  let ubicacionPayload;

  // CANCELADO no requiere ubicación
  if (_estadoSeleccionado === 'CANCELADO') {
    ubicacionPayload = { reusar_ubicacion_anterior: false };
  } else if (reusar) {
    ubicacionPayload = { reusar_ubicacion_anterior: true };
  } else {
    const checks = [
      ['estado-calle',    validateCalle,       'calle de ubicación'],
      ['estado-numero',   validateNumero,      'número de ubicación'],
      ['estado-cp',       validateCP,          'código postal de ubicación'],
      ['estado-ciudad',   validateTextoSimple, 'ciudad de ubicación'],
      ['estado-provincia',validateTextoSimple, 'provincia de ubicación'],
    ];
    let valid = true;
    let firstInvalid = null;
    for (const [id, fn, label] of checks) {
      const input = document.getElementById(id);
      const error = document.getElementById('err-' + id);
      const msg = fn(input.value, label);
      if (msg) {
        input.setAttribute('aria-invalid', 'true');
        error.textContent = msg;
        error.classList.add('visible');
        if (valid) firstInvalid = id;
        valid = false;
      } else {
        input.setAttribute('aria-invalid', 'false');
        error.classList.remove('visible');
      }
    }
    if (!valid) {
      const reusarWrap = document.getElementById('reusar-wrap');
      const errGeneral = document.getElementById('err-ubicacion-general');
      if (reusarWrap.style.display !== 'none') {
        errGeneral.textContent = "Completá la nueva ubicación o marcá 'Mantener la dirección actual'.";
        errGeneral.classList.add('visible');
      }
      document.getElementById(firstInvalid).focus();
      return;
    }
    document.getElementById('err-ubicacion-general').classList.remove('visible');

    ubicacionPayload = {
      reusar_ubicacion_anterior: false,
      nueva_ubicacion: {
        calle:         document.getElementById('estado-calle').value.trim(),
        numero:        document.getElementById('estado-numero').value.trim(),
        ciudad:        document.getElementById('estado-ciudad').value.trim(),
        provincia:     document.getElementById('estado-provincia').value.trim(),
        codigo_postal: document.getElementById('estado-cp').value.trim(),
      },
    };
  }

  const endpoint = `${API_BASE}/envios/${encodeURIComponent(_trackingIdEnCambioEstado)}/estado`;
  const payload  = { nuevo_estado: _estadoSeleccionado, ...ubicacionPayload };

  const btn = document.getElementById('btn-confirmar-estado');
  btn.disabled = true;
  btn.textContent = 'Guardando…';

  try {
    const res = await fetch(endpoint, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      alert(typeof err.detail === 'string' ? err.detail : 'Error al cambiar el estado.');
      return;
    }
    const data       = await res.json();
    const tid        = _trackingIdEnCambioEstado;
    const nuevoLabel = BADGE_LABEL[data.estado] || data.estado;
    closeEstado();
    showToast('Estado actualizado', `${tid} → ${nuevoLabel}`, false);
    cargarEnvios(currentQuery, currentPage);
  } catch (err) {
    console.error('Error al cambiar estado:', err);
    alert('No se pudo cambiar el estado. Verificá que el backend esté corriendo.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Confirmar cambio';
  }
}

function openConfirmCancelar() {
  document.getElementById('confirm-cancelar-tid').textContent = _trackingIdEnCambioEstado;
  document.getElementById('confirm-cancelar-overlay').style.display = 'flex';
}

function closeConfirmCancelar() {
  document.getElementById('confirm-cancelar-overlay').style.display = 'none';
}

async function confirmarCancelar() {
  closeConfirmCancelar();
  await _ejecutarCambioEstado();
}


// ─── Edición de envío ─────────────────────────────────────────────────────────
let _trackingIdEnEdicion = null;

function openEdit(trackingId, envio) {
  _trackingIdEnEdicion = trackingId;
  document.getElementById('edit-modal-tracking-id').textContent = trackingId;

  // Pre-fill contacto
  document.getElementById('edit-destinatario').value      = envio.destinatario;
  document.getElementById('edit-destino-calle').value     = envio.direccion_destino.calle;
  document.getElementById('edit-destino-numero').value    = envio.direccion_destino.numero;
  document.getElementById('edit-destino-cp').value        = envio.direccion_destino.codigo_postal;
  document.getElementById('edit-destino-ciudad').value    = envio.direccion_destino.ciudad;
  document.getElementById('edit-destino-provincia').value = envio.direccion_destino.provincia;

  // Pre-fill operativo
  document.getElementById('edit-fecha-entrega').value = envio.fecha_entrega_estimada;
  document.getElementById('edit-prob-retraso').value  = envio.probabilidad_retraso ?? '';

  switchEditTab('contacto');
  _clearEditErrors();

  document.getElementById('edit-overlay').style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeEdit() {
  document.getElementById('edit-overlay').style.display = 'none';
  document.body.style.overflow = '';
  _trackingIdEnEdicion = null;
}

function switchEditTab(tab) {
  ['contacto', 'operativo'].forEach(t => {
    document.getElementById(`edit-tab-${t}`).classList.toggle('active', t === tab);
    document.getElementById(`edit-panel-${t}`).style.display = t === tab ? '' : 'none';
  });
}

function _clearEditErrors() {
  const ids = [
    'edit-destinatario', 'edit-destino-calle', 'edit-destino-numero',
    'edit-destino-cp', 'edit-destino-ciudad', 'edit-destino-provincia',
    'edit-fecha-entrega', 'edit-prob-retraso',
  ];
  ids.forEach(id => {
    const input = document.getElementById(id);
    const error = document.getElementById('err-' + id);
    if (input) input.setAttribute('aria-invalid', 'false');
    if (error) error.classList.remove('visible');
  });
}

function _setEditFieldError(id, msg) {
  const input = document.getElementById(id);
  const error = document.getElementById('err-' + id);
  input.setAttribute('aria-invalid', 'true');
  error.textContent = msg;
  error.classList.add('visible');
}

function _clearEditField(id) {
  const input = document.getElementById(id);
  const error = document.getElementById('err-' + id);
  if (input) input.setAttribute('aria-invalid', 'false');
  if (error) error.classList.remove('visible');
}

async function submitEditContacto() {
  const checks = [
    ['edit-destinatario',    validateText,        'nombre del destinatario'],
    ['edit-destino-calle',   validateCalle,       'calle de destino'],
    ['edit-destino-numero',  validateNumero,      'número de destino'],
    ['edit-destino-cp',      validateCP,          'código postal de destino'],
    ['edit-destino-ciudad',  validateTextoSimple, 'ciudad de destino'],
    ['edit-destino-provincia', validateTextoSimple, 'provincia de destino'],
  ];

  let valid = true;
  let firstInvalid = null;
  for (const [id, fn, label] of checks) {
    const input = document.getElementById(id);
    const msg = fn(input.value, label);
    if (msg) {
      _setEditFieldError(id, msg);
      if (valid) firstInvalid = id;
      valid = false;
    } else {
      _clearEditField(id);
    }
  }
  if (!valid) { document.getElementById(firstInvalid).focus(); return; }

  const payload = {
    destinatario: document.getElementById('edit-destinatario').value.trim(),
    direccion_destino: {
      calle:         document.getElementById('edit-destino-calle').value.trim(),
      numero:        document.getElementById('edit-destino-numero').value.trim(),
      ciudad:        document.getElementById('edit-destino-ciudad').value.trim(),
      provincia:     document.getElementById('edit-destino-provincia').value.trim(),
      codigo_postal: document.getElementById('edit-destino-cp').value.trim(),
    },
  };

  const btn = document.getElementById('btn-guardar-contacto');
  btn.disabled = true;
  btn.textContent = 'Guardando…';

  try {
    const res = await fetch(`${API_BASE}/envios/${encodeURIComponent(_trackingIdEnEdicion)}/contacto`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (await handleApiError(res)) return;
    if (!res.ok) {
      const err = await res.json();
      if (Array.isArray(err.detail)) {
        const fieldMap = {
          destinatario: 'edit-destinatario', calle: 'edit-destino-calle',
          numero: 'edit-destino-numero', codigo_postal: 'edit-destino-cp',
          ciudad: 'edit-destino-ciudad', provincia: 'edit-destino-provincia',
        };
        err.detail.forEach(d => {
          const id = fieldMap[d.loc?.[d.loc.length - 1]];
          if (id) _setEditFieldError(id, d.msg);
        });
      }
      return;
    }
    const tid = _trackingIdEnEdicion;
    closeEdit();
    showToast(tid, 'Datos de contacto actualizados');
    cargarEnvios(currentQuery, currentPage);
  } catch (err) {
    console.error('Error al actualizar contacto:', err);
    alert('No se pudo actualizar el envío. Verificá que el backend esté corriendo.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Guardar cambios';
  }
}

async function submitEditOperativo() {
  const fechaInput = document.getElementById('edit-fecha-entrega');
  const fechaMsg = validateFecha(fechaInput.value, 'fecha estimada de entrega');
  if (fechaMsg) {
    _setEditFieldError('edit-fecha-entrega', fechaMsg);
    fechaInput.focus();
    return;
  }
  _clearEditField('edit-fecha-entrega');

  const probVal = document.getElementById('edit-prob-retraso').value.trim();
  const probNum = probVal !== '' ? parseFloat(probVal) : null;
  if (probNum === null || isNaN(probNum)) {
    _setEditFieldError('edit-prob-retraso', 'Ingresá la probabilidad de retraso.');
    document.getElementById('edit-prob-retraso').focus();
    return;
  }
  if (probNum < 0 || probNum > 1) {
    _setEditFieldError('edit-prob-retraso', 'La probabilidad debe ser un número entre 0 y 1.');
    document.getElementById('edit-prob-retraso').focus();
    return;
  }
  _clearEditField('edit-prob-retraso');

  const payload = {
    fecha_entrega_estimada: fechaInput.value,
    probabilidad_retraso:   probNum,
  };

  const btn = document.getElementById('btn-guardar-operativo');
  btn.disabled = true;
  btn.textContent = 'Guardando…';

  try {
    const res = await fetch(`${API_BASE}/envios/${encodeURIComponent(_trackingIdEnEdicion)}/operativo`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });
    if (await handleApiError(res)) return;
    if (!res.ok) {
      const err = await res.json();
      if (Array.isArray(err.detail)) {
        err.detail.forEach(d => {
          if (d.loc?.[d.loc.length - 1] === 'fecha_entrega_estimada') {
            _setEditFieldError('edit-fecha-entrega', d.msg);
          }
        });
      }
      return;
    }
    const tid = _trackingIdEnEdicion;
    closeEdit();
    showToast(tid, 'Datos operativos actualizados');
    cargarEnvios(currentQuery, currentPage);
  } catch (err) {
    console.error('Error al actualizar operativo:', err);
    alert('No se pudo actualizar el envío. Verificá que el backend esté corriendo.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Guardar cambios';
  }
}

// ─── Definición de campos y sus validaciones ──────────────────────────────────
const FIELDS = {
  remitente:           { label: 'nombre del remitente',      validate: validateText },
  destinatario:        { label: 'nombre del destinatario',   validate: validateText },
  'fecha-entrega':     { label: 'fecha estimada de entrega', validate: validateFecha },
  'origen-calle':      { label: 'calle de origen',           validate: validateCalle },
  'origen-numero':     { label: 'número de origen',          validate: validateNumero },
  'origen-cp':         { label: 'código postal de origen',   validate: validateCP },
  'origen-ciudad':     { label: 'ciudad de origen',          validate: validateTextoSimple },
  'origen-provincia':  { label: 'provincia de origen',       validate: validateTextoSimple },
  'destino-calle':     { label: 'calle de destino',          validate: validateCalle },
  'destino-numero':    { label: 'número de destino',         validate: validateNumero },
  'destino-cp':        { label: 'código postal de destino',  validate: validateCP },
  'destino-ciudad':    { label: 'ciudad de destino',         validate: validateTextoSimple },
  'destino-provincia': { label: 'provincia de destino',      validate: validateTextoSimple },
};

// ─── Funciones de validación ──────────────────────────────────────────────────
function validateText(val, label) {
  if (!val.trim()) return `Ingresá el ${label}.`;
  return null;
}

function validateCalle(val, label) {
  if (!val.trim()) return `Ingresá la ${label}.`;
  if (val.trim().length < 2) return `La ${label} debe tener al menos 2 caracteres.`;
  if (/^\d+$/.test(val.trim())) return `La ${label} debe contener letras.`;
  return null;
}

function validateNumero(val, label) {
  if (!val.trim()) return `Ingresá el ${label}.`;
  if (!/^\d+$/.test(val.trim())) return `El ${label} debe ser un valor numérico.`;
  return null;
}

function validateCP(val, label) {
  if (!val.trim()) return `Ingresá el ${label}.`;
  if (!/^\d+$/.test(val.trim())) return `El ${label} debe ser un valor numérico.`;
  return null;
}

function validateTextoSimple(val, label) {
  if (!val.trim()) return `Ingresá la ${label}.`;
  if (val.trim().length < 2) return `La ${label} debe tener al menos 2 caracteres.`;
  if (/[^a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]/.test(val.trim())) return `La ${label} solo debe contener letras y espacios.`;
  return null;
}

function validateFecha(val, label) {
  if (!val) return `Ingresá la ${label}.`;
  const hoy = new Date(); hoy.setHours(0, 0, 0, 0);
  const fecha = new Date(val + 'T00:00:00');
  if (isNaN(fecha.getTime())) return `La ${label} no es válida.`;
  if (fecha < hoy) return `La ${label} no puede ser anterior a hoy.`;
  return null;
}

// ─── Validar un campo individual ──────────────────────────────────────────────
function validateField(id) {
  const input = document.getElementById(id);
  const error = document.getElementById('err-' + id);
  const field = FIELDS[id];
  if (!input || !error || !field) return true;

  const msg = field.validate(input.value, field.label);
  if (msg) {
    input.setAttribute('aria-invalid', 'true');
    error.textContent = msg;
    error.classList.add('visible');
    return false;
  }
  input.setAttribute('aria-invalid', 'false');
  error.classList.remove('visible');
  return true;
}

function clearFieldError(id) {
  const input = document.getElementById(id);
  const error = document.getElementById('err-' + id);
  if (!input || !error) return;
  input.setAttribute('aria-invalid', 'false');
  error.classList.remove('visible');
}

// ─── Submit → POST /envios ────────────────────────────────────────────────────
async function submitForm() {
  const allFields = Object.keys(FIELDS);
  const valid = allFields.map(validateField).every(Boolean);

  if (!valid) {
    const first = allFields.find(id => {
      const el = document.getElementById(id);
      return el && el.getAttribute('aria-invalid') === 'true';
    });
    if (first) document.getElementById(first).focus();
    return;
  }

  // Validar que origen y destino no sean la misma dirección
  const g = id => document.getElementById(id).value.trim().toLowerCase();
  const gExact = id => document.getElementById(id).value.trim();
  const mismaDireccion = (
    g('origen-calle')     === g('destino-calle')     &&
    gExact('origen-numero') === gExact('destino-numero') &&
    g('origen-ciudad')    === g('destino-ciudad')    &&
    g('origen-provincia') === g('destino-provincia') &&
    gExact('origen-cp')    === gExact('destino-cp')
  );
  if (mismaDireccion) {
    const errEl = document.getElementById('err-destino-calle');
    errEl.textContent = 'La dirección de destino no puede ser igual a la de origen.';
    errEl.classList.add('visible');
    document.getElementById('destino-calle').setAttribute('aria-invalid', 'true');
    document.getElementById('destino-calle').focus();
    return;
  }

  const probVal = document.getElementById('prob-retraso').value.trim();
  const probNum = probVal !== '' ? parseFloat(probVal) : null;
  const errProb = document.getElementById('err-prob-retraso');
  if (probNum === null || isNaN(probNum)) {
    errProb.textContent = 'Ingresá la probabilidad de retraso.';
    errProb.classList.add('visible');
    document.getElementById('prob-retraso').setAttribute('aria-invalid', 'true');
    document.getElementById('prob-retraso').focus();
    return;
  }
  if (probNum < 0 || probNum > 1) {
    errProb.textContent = 'La probabilidad debe ser un número entre 0 y 1.';
    errProb.classList.add('visible');
    document.getElementById('prob-retraso').setAttribute('aria-invalid', 'true');
    document.getElementById('prob-retraso').focus();
    return;
  }
  errProb.classList.remove('visible');
  document.getElementById('prob-retraso').setAttribute('aria-invalid', 'false');

  const payload = {
    remitente:              document.getElementById('remitente').value.trim(),
    destinatario:           document.getElementById('destinatario').value.trim(),
    probabilidad_retraso:   probNum,
    fecha_entrega_estimada: document.getElementById('fecha-entrega').value,
    direccion_origen: {
      calle:         document.getElementById('origen-calle').value.trim(),
      numero:        document.getElementById('origen-numero').value.trim(),
      ciudad:        document.getElementById('origen-ciudad').value.trim(),
      provincia:     document.getElementById('origen-provincia').value.trim(),
      codigo_postal: document.getElementById('origen-cp').value.trim(),
    },
    direccion_destino: {
      calle:         document.getElementById('destino-calle').value.trim(),
      numero:        document.getElementById('destino-numero').value.trim(),
      ciudad:        document.getElementById('destino-ciudad').value.trim(),
      provincia:     document.getElementById('destino-provincia').value.trim(),
      codigo_postal: document.getElementById('destino-cp').value.trim(),
    },
  };

  const btnSubmit = document.querySelector('#alta-form button[type="submit"]');
  btnSubmit.disabled = true;
  btnSubmit.textContent = 'Registrando…';

  try {
    const res = await fetch(`${API_BASE}/envios`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });

    if (await handleApiError(res)) return;

    if (!res.ok) {
      const err = await res.json();
      console.error('Error del servidor:', err);
      if (Array.isArray(err.detail)) {
        err.detail.forEach(d => {
          const campo = d.loc?.[d.loc.length - 1];
          const errorEl = document.getElementById('err-' + campo);
          if (errorEl) {
            errorEl.textContent = d.msg;
            errorEl.classList.add('visible');
            document.getElementById(campo)?.setAttribute('aria-invalid', 'true');
          }
        });
      }
      return;
    }

    const envio = await res.json();
    showToast(envio.tracking_id);
    setTimeout(() => showView('list'), 1800);

  } catch (err) {
    console.error('Error de red:', err);
    alert('No se pudo conectar con el servidor. Verificá que el backend esté corriendo.');
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.textContent = 'Registrar envío';
  }
}

// ─── Reset form ───────────────────────────────────────────────────────────────
function resetForm() {
  Object.keys(FIELDS).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
    clearFieldError(id);
  });
  const probEl = document.getElementById('prob-retraso');
  if (probEl) probEl.value = '';
  const errProb = document.getElementById('err-prob-retraso');
  if (errProb) errProb.classList.remove('visible');
  document.getElementById('tracking-display').textContent = '(se asignará al registrar)';
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function showToast(tid, titulo = 'Envío registrado correctamente') {
  const toast = document.getElementById('toast');
  document.getElementById('toast-title').textContent = titulo;
  document.getElementById('toast-sub').textContent   = tid;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3500);
}

// ─── Util ─────────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ─── Alta de usuario (ADMINISTRADOR) ─────────────────────────────────────────
function _setAdminFieldError(id, msg) {
  const input = document.getElementById(id);
  const error = document.getElementById('err-' + id);
  if (input) input.setAttribute('aria-invalid', 'true');
  if (error) { error.textContent = msg; error.classList.add('visible'); }
}

function _clearAdminFieldError(id) {
  const input = document.getElementById(id);
  const error = document.getElementById('err-' + id);
  if (input) input.setAttribute('aria-invalid', 'false');
  if (error) error.classList.remove('visible');
}

async function registrarUsuario() {
  const emailEl = document.getElementById('nuevo-email');
  const passEl  = document.getElementById('nuevo-password');
  const rolEl   = document.getElementById('nuevo-rol');
  const btn     = document.getElementById('btn-registrar-usuario');
  const successEl = document.getElementById('admin-registro-success');
  const errorEl   = document.getElementById('admin-registro-error');

  // Limpiar mensajes anteriores
  successEl.style.display = 'none';
  errorEl.style.display   = 'none';
  ['nuevo-email', 'nuevo-password', 'nuevo-rol'].forEach(_clearAdminFieldError);

  // CA-5: validar campos obligatorios
  let valid = true;
  if (!emailEl.value.trim()) {
    _setAdminFieldError('nuevo-email', 'El email es obligatorio.');
    valid = false;
  }
  if (!passEl.value) {
    _setAdminFieldError('nuevo-password', 'La contraseña es obligatoria.');
    valid = false;
  } else if (passEl.value.length < 8) {
    _setAdminFieldError('nuevo-password', 'La contraseña debe tener al menos 8 caracteres.');
    valid = false;
  }
  // CA-4: rol obligatorio
  if (!rolEl.value) {
    _setAdminFieldError('nuevo-rol', 'El rol es obligatorio.');
    valid = false;
  }
  if (!valid) return;

  btn.disabled = true;
  btn.textContent = 'Registrando…';

  try {
    const res = await fetch(`${API_BASE}/usuarios`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        email:      emailEl.value.trim(),
        password:   passEl.value,
        rol_nombre: rolEl.value,
      }),
    });

    if (await handleApiError(res)) return;

    if (res.status === 409) {
      // CA-3: email ya registrado
      const data = await res.json();
      errorEl.textContent = data.detail || 'El email ya está registrado en el sistema.';
      errorEl.style.display = '';
      return;
    }

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const msg = Array.isArray(data.detail)
        ? data.detail.map(e => e.msg).join(' · ')
        : (data.detail || 'Ocurrió un error al registrar el usuario.');
      errorEl.textContent = msg;
      errorEl.style.display = '';
      return;
    }
    

    // CA-2: registro exitoso
    const data = await res.json();
    successEl.textContent = `Usuario ${escHtml(data.email)} registrado correctamente como ${escHtml(data.nombre_rol)}.`;
    successEl.style.display = '';
    document.getElementById('form-alta-usuario').reset();

  } catch (err) {
    console.error('Error al registrar usuario:', err);
    errorEl.textContent = 'No se pudo conectar con el servidor. Verificá que el sistema esté disponible.';
    errorEl.style.display = '';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Registrar usuario';
  }
}

// ─── Auditoria (ADMINISTRADOR) ─────────────────────────────────────────

async function buscarAuditoria() {
    const afectadoEl = document.getElementById('filtro-afectado');
    const ejecutorEl = document.getElementById('filtro-ejecutor');
    const msgEl = document.getElementById('auditoria-mensaje');
    const tablaBody = document.querySelector('#tabla-auditoria tbody');

    // limpiar mensajes y tabla
    msgEl.style.display = 'none';
    msgEl.textContent = '';
    tablaBody.innerHTML = '';

    const params = new URLSearchParams();

    if (afectadoEl.value.trim()) params.append('usuario_afectado_uuid', afectadoEl.value.trim());
    if (ejecutorEl.value.trim()) params.append('usuario_ejecutor_uuid', ejecutorEl.value.trim());
    const res = await fetch(`${API_BASE}/auditoria/eventos?${params.toString()}`, {
    headers: authHeaders()
    });
    try {
        const res = await fetch(`${API_BASE}/auditoria/eventos?${params.toString()}`, {
            method: 'GET',
            headers: { ...authHeaders() }
        });

        if (await handleApiError(res)) return;

        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            msgEl.textContent = data.detail || 'Ocurrió un error al obtener la auditoría.';
            msgEl.style.display = '';
            return;
        }

        const data = await res.json();

        if (!data.length) {
            msgEl.textContent = 'No se encontraron registros.';
            msgEl.style.display = '';
            return;
        }

        // rellenar tabla
        data.forEach(item => {
            const tr = document.createElement('tr');

            tr.innerHTML = `
                <td>${escHtml(item.accion || '')}</td>
                <td>${escHtml(item.usuario_ejecutor_uuid || '')}</td>
                <td>${escHtml(item.usuario_afectado_uuid || '')}</td>
                <td>${escHtml(item.estado_inicial || '')}</td>
                <td>${escHtml(item.estado_final || '')}</td>
                <td>${escHtml(item.fecha || '')}</td>
            `;

            tablaBody.appendChild(tr);
        });

    } catch (err) {
        console.error("Error al buscar auditoría:", err);
        msgEl.textContent = 'No se pudo conectar con el servidor. Verificá que esté disponible.';
        msgEl.style.display = '';
    }
}


// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Inicializar aplicación (verificar sesión)
  initApp();

  // Eventos del form de login
  ['login-email', 'login-password'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => _clearLoginFieldError(id));
  });

  // Enter en el input de consulta pública
  const trackInput = document.getElementById('public-track-input');
  if (trackInput) {
    trackInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') buscarPublico();
    });
  }

  // Eventos de validación en formulario de alta
  Object.keys(FIELDS).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => clearFieldError(id));
  });

  // Limpiar errores del formulario admin al editar campos
  ['nuevo-email', 'nuevo-password', 'nuevo-rol'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => _clearAdminFieldError(id));
  });

  // Búsqueda con debounce
  const searchEl = document.getElementById('search-input');
  if (searchEl) {
    let searchTimer;
    searchEl.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(
        () => cargarEnvios(searchEl.value, 1),
        300
      );
    });
  }

  // Escape para cerrar modales
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      closeEdit();
      closeConfirmDelete();
      closeDetalle();
    }
  });
});

document.addEventListener('DOMContentLoaded', function() {

  document.getElementById('modal-alta-usuario').addEventListener('click', function(e) {
    if (e.target === this) cerrarModalAlta();
  });

});

  function cerrarModalAlta() {
    document.getElementById('modal-alta-usuario').style.display = 'none';
    document.getElementById('form-alta-usuario').reset();
    document.getElementById('admin-registro-success').style.display = 'none';
    document.getElementById('admin-registro-error').style.display = 'none';
  }

function mostrarAuditoria() {
    document.getElementById("auditoria-container").style.display = "block";
    buscarAuditoria(); // carga inicial sin filtros (CA-2)
}

