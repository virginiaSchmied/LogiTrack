'use strict';

// ─── Datos mockeados ───────────────────────────────────────────────────────
let envios = [
  {
    id: 'LT-00000001',
    remitente: 'Carlos Ruiz',
    destinatario: 'Ana Torres',
    origen: { calle: 'Belgrano', numero: '123', ciudad: 'Buenos Aires', provincia: 'CABA', cp: '1092' },
    destino: { calle: 'Thames', numero: '456', ciudad: 'Buenos Aires', provincia: 'CABA', cp: '1414' },
    estado: 'ENTREGADO',
    fechaEntrega: '2025-03-10',
  },
  {
    id: 'LT-00000002',
    remitente: 'Sofía Herrera',
    destinatario: 'Lucas Medina',
    origen: { calle: 'Corrientes', numero: '890', ciudad: 'Rosario', provincia: 'Santa Fe', cp: '2000' },
    destino: { calle: 'Colón', numero: '321', ciudad: 'Córdoba', provincia: 'Córdoba', cp: '5000' },
    estado: 'EN_TRANSITO',
    fechaEntrega: '2025-03-20',
  },
  {
    id: 'LT-00000003',
    remitente: 'Empresa ABC',
    destinatario: 'Pedro Gómez',
    origen: { calle: 'San Martín', numero: '1200', ciudad: 'Mendoza', provincia: 'Mendoza', cp: '5500' },
    destino: { calle: 'Rivadavia', numero: '700', ciudad: 'San Luis', provincia: 'San Luis', cp: '5700' },
    estado: 'REGISTRADO',
    fechaEntrega: '2025-03-25',
  },
  {
    id: 'LT-00000004',
    remitente: 'Laura Vidal',
    destinatario: 'Martín Cruz',
    origen: { calle: 'Vélez Sársfield', numero: '50', ciudad: 'Córdoba', provincia: 'Córdoba', cp: '5000' },
    destino: { calle: 'Maipú', numero: '300', ciudad: 'Tucumán', provincia: 'Tucumán', cp: '4000' },
    estado: 'RETRASADO',
    fechaEntrega: '2025-03-17',
  },
];

let counter = envios.length + 1;

// ─── Mapa de badges por estado ───────────────────────────────────────────────
const BADGE_CLASS = {
  'REGISTRADO':    'badge-registrado',
  'EN_TRANSITO':   'badge-transito',
  'EN_SUCURSAL':   'badge-sucursal',
  'EN_DISTRIBUCION': 'badge-distribucion',
  'ENTREGADO':     'badge-entregado',
  'RETRASADO':     'badge-retrasado',
  'CANCELADO':     'badge-cancelado',
  'BLOQUEADO':     'badge-bloqueado',
  'ELIMINADO':     'badge-eliminado',
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

// ─── Generar tracking ID ─────────────────────────────────────────────────────
function generateTID() {
  const n = String(counter).padStart(8, '0');
  return `LT-${n}`;
}

// ─── Navegación ──────────────────────────────────────────────────────────────
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
    renderTable();
  }
}

// ─── Render tabla ─────────────────────────────────────────────────────────────
function renderTable(filter = '') {
  const tbody = document.getElementById('table-body');
  const table = document.getElementById('envios-table');
  const empty = document.getElementById('empty-state');
  const noRes = document.getElementById('no-results');
  const chip  = document.getElementById('count-chip');

  chip.textContent = envios.length;

  const q = filter.toLowerCase().trim();
  const filtered = q
    ? envios.filter(e =>
        e.id.toLowerCase().includes(q) ||
        e.destinatario.toLowerCase().includes(q) ||
        e.remitente.toLowerCase().includes(q)
      )
    : envios;

  if (envios.length === 0) {
    table.style.display = 'none'; empty.style.display = ''; noRes.style.display = 'none'; return;
  }
  if (filtered.length === 0) {
    table.style.display = 'none'; empty.style.display = 'none'; noRes.style.display = ''; return;
  }

  empty.style.display = 'none';
  noRes.style.display = 'none';
  table.style.display = '';

  tbody.innerHTML = filtered.map(e => `
    <tr>
      <td data-label="Tracking ID"><span class="tid-text">${escHtml(e.id)}</span></td>
      <td data-label="Remitente">${escHtml(e.remitente)}</td>
      <td data-label="Destinatario">${escHtml(e.destinatario)}</td>
      <td data-label="Ciudad Origen" class="sub-text">${escHtml(e.origen.ciudad)}, ${escHtml(e.origen.provincia)}</td>
      <td data-label="Ciudad Destino" class="sub-text">${escHtml(e.destino.ciudad)}, ${escHtml(e.destino.provincia)}</td>
      <td data-label="Estado"><span class="badge ${BADGE_CLASS[e.estado] || 'badge-registrado'}">${escHtml(BADGE_LABEL[e.estado] || e.estado)}</span></td>
      <td data-label="Entrega estimada" class="mono-text">${escHtml(formatFecha(e.fechaEntrega))}</td>
    </tr>
  `).join('');
}

function formatFecha(iso) {
  if (!iso) return '-';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

// ─── Filtro en tiempo real ────────────────────────────────────────────────────
function filterTable() {
  renderTable(document.getElementById('search-input').value);
}

// ─── Definición de campos y sus validaciones ──────────────────────────────────
const FIELDS = {
  remitente:          { label: 'nombre del remitente',       validate: validateText },
  destinatario:       { label: 'nombre del destinatario',    validate: validateText },
  'fecha-entrega':    { label: 'fecha estimada de entrega',  validate: validateFecha },
  'origen-calle':     { label: 'calle de origen',            validate: validateCalle },
  'origen-numero':    { label: 'número de origen',           validate: validateNumero },
  'origen-cp':        { label: 'código postal de origen',    validate: validateCP },
  'origen-ciudad':    { label: 'ciudad de origen',           validate: validateTextoSimple },
  'origen-provincia': { label: 'provincia de origen',        validate: validateTextoSimple },
  'destino-calle':    { label: 'calle de destino',           validate: validateCalle },
  'destino-numero':   { label: 'número de destino',          validate: validateNumero },
  'destino-cp':       { label: 'código postal de destino',   validate: validateCP },
  'destino-ciudad':   { label: 'ciudad de destino',          validate: validateTextoSimple },
  'destino-provincia':{ label: 'provincia de destino',       validate: validateTextoSimple },
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

// ─── Validar un campo individual ─────────────────────────────────────────────
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

// ─── Submit ───────────────────────────────────────────────────────────────────
function submitForm() {
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

  const tid = generateTID();
  envios.unshift({
    id: tid,
    remitente:    document.getElementById('remitente').value.trim(),
    destinatario: document.getElementById('destinatario').value.trim(),
    fechaEntrega: document.getElementById('fecha-entrega').value,
    origen: {
      calle:    document.getElementById('origen-calle').value.trim(),
      numero:   document.getElementById('origen-numero').value.trim(),
      ciudad:   document.getElementById('origen-ciudad').value.trim(),
      provincia:document.getElementById('origen-provincia').value.trim(),
      cp:       document.getElementById('origen-cp').value.trim(),
    },
    destino: {
      calle:    document.getElementById('destino-calle').value.trim(),
      numero:   document.getElementById('destino-numero').value.trim(),
      ciudad:   document.getElementById('destino-ciudad').value.trim(),
      provincia:document.getElementById('destino-provincia').value.trim(),
      cp:       document.getElementById('destino-cp').value.trim(),
    },
    estado: 'REGISTRADO',
  });

  counter++;
  showToast(tid);
  setTimeout(() => showView('list'), 1800);
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
    searchTimer = setTimeout(filterTable, 120);
  });

  renderTable();
});