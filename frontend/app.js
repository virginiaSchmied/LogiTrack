'use strict';

// ─── Config ───────────────────────────────────────────────────────────────────
const API_BASE = "";

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

// ─── Navegación ───────────────────────────────────────────────────────────────
function showView(viewName) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-tabs button').forEach(b => {
    b.classList.remove('active');
    b.removeAttribute('aria-current');
  });

  document.getElementById('view-' + viewName).classList.add('active');
  const tab = document.getElementById('tab-' + viewName);
  tab.classList.add('active');
  tab.setAttribute('aria-current', 'page');

  if (viewName === 'form') resetForm();
  if (viewName === 'list') {
    document.getElementById('search-input').value = '';
    cargarEnvios();
  }
}

// ─── Carga de envíos desde la API ─────────────────────────────────────────────
async function cargarEnvios(q = '') {
  const tbody = document.getElementById('table-body');
  const table = document.getElementById('envios-table');
  const empty = document.getElementById('empty-state');
  const noRes = document.getElementById('no-results');
  const chip  = document.getElementById('count-chip');

  try {
    const url = q.trim()
      ? `${API_BASE}/envios?q=${encodeURIComponent(q.trim())}`
      : `${API_BASE}/envios`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`Error ${res.status}`);

    const data = await res.json();
    const envios = data.items;

    chip.textContent = data.total;

    if (data.total === 0 && !q.trim()) {
      table.style.display = 'none';
      empty.style.display = '';
      noRes.style.display = 'none';
      empty.querySelector('.e-title').textContent = 'No hay envíos registrados';
      empty.querySelector('.e-desc').textContent  = 'Registrá el primer envío usando el botón de arriba.';
      return;
    }

    if (envios.length === 0) {
      table.style.display = 'none';
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
        <td data-label="Entrega estimada" class="mono-text">${escHtml(formatFecha(e.fecha_entrega_estimada))}</td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Error al cargar envíos:', err);
    chip.textContent = '—';
    table.style.display = 'none';
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

// ─── Modal de detalle ─────────────────────────────────────────────────────────
async function openDetalle(trackingId) {
  const overlay  = document.getElementById('modal-overlay');
  const body     = document.getElementById('modal-body');
  const tidEl    = document.getElementById('modal-tracking-id');
  const estadoEl = document.getElementById('modal-estado-badge');

  tidEl.textContent  = trackingId;
  estadoEl.innerHTML = '';
  body.innerHTML     = '<div class="modal-loading">Cargando detalle…</div>';
  overlay.style.display = 'flex';
  document.body.style.overflow = 'hidden';

  try {
    const res = await fetch(`${API_BASE}/envios/${encodeURIComponent(trackingId)}`);
    if (!res.ok) throw new Error(`Error ${res.status}`);
    const e = await res.json();

    estadoEl.innerHTML = `<span class="badge ${BADGE_CLASS[e.estado] || 'badge-registrado'}">${escHtml(BADGE_LABEL[e.estado] || e.estado)}</span>`;

    body.innerHTML = `
      <div class="detail-grid">

        <div class="detail-section">
          <div class="section-title">Datos generales</div>
          <dl class="detail-list">
            <div class="dl-row"><dt>Remitente</dt><dd>${escHtml(e.remitente)}</dd></div>
            <div class="dl-row"><dt>Destinatario</dt><dd>${escHtml(e.destinatario)}</dd></div>
            <div class="dl-row"><dt>Prioridad</dt><dd>${e.prioridad ? escHtml(e.prioridad) : '<span class="sub-text">No asignada</span>'}</dd></div>
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
  document.body.style.overflow = '';
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

  const payload = {
    remitente:              document.getElementById('remitente').value.trim(),
    destinatario:           document.getElementById('destinatario').value.trim(),
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

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
  document.getElementById('tracking-display').textContent = '(se asignará al registrar)';
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function showToast(tid) {
  const toast = document.getElementById('toast');
  document.getElementById('toast-sub').textContent = tid;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3500);
}

// ─── Util ─────────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  Object.keys(FIELDS).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', () => clearFieldError(id));
  });

  let searchTimer;
  document.getElementById('search-input').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(
      () => cargarEnvios(document.getElementById('search-input').value),
      300
    );
  });

  cargarEnvios();

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDetalle();
  });
});