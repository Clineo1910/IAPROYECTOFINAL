const mensajesEl = document.getElementById('chat-mensajes');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-texto');
const btnRolTutor = document.getElementById('btn-rol-tutor');
const btnRolPadre = document.getElementById('btn-rol-padre');
const chatRolLabel = document.getElementById('chat-rol-label');
const chatChips = document.getElementById('chat-chips');

let alumnosCache = [];
let protocolosCache = [];
let filtroNivel = 'TODOS';
let textoBusqueda = '';
let rolActual = 'tutor';

// Render seguro sin innerHTML (soporta **negrita** usando createTextNode)
function renderTextoSeguro(contenedor, texto) {
  contenedor.textContent = '';
  const partes = String(texto || '').split(/(\*\*[^*]+\*\*)/g);
  partes.forEach((parte) => {
    if (parte.startsWith('**') && parte.endsWith('**') && parte.length > 4) {
      const strong = document.createElement('strong');
      strong.textContent = parte.slice(2, -2);
      contenedor.appendChild(strong);
    } else {
      contenedor.appendChild(document.createTextNode(parte));
    }
  });
}

function agregarBurbuja(autor, texto, esUsuario) {
  const wrap = document.createElement('div');
  wrap.className = `bubble ${esUsuario ? 'bubble-user' : 'bubble-bot'}`;

  const meta = document.createElement('span');
  meta.className = 'bubble-meta';
  meta.textContent = autor;

  const body = document.createElement('span');
  renderTextoSeguro(body, texto);

  wrap.appendChild(meta);
  wrap.appendChild(body);
  mensajesEl.appendChild(wrap);
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
  return body;
}

async function enviarConsultaAlAgente(texto) {
  agregarBurbuja(rolActual === 'tutor' ? 'Tutor' : 'Padre / Apoderado', texto, true);
  const cuerpoBot = agregarBurbuja('SIGE-Bot · Consultando MCP', 'Analizando datos en PostgreSQL...', false);
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensaje: texto }),
    });
    const datos = await r.json();
    cuerpoBot.previousSibling.textContent = 'SIGE-Bot · Respuesta verificada';
    renderTextoSeguro(cuerpoBot, datos.respuesta);
    // Refrescar intervenciones y Rayos X MCP
    cargarDashboard();
    cargarMcpLogs();
  } catch (_err) {
    renderTextoSeguro(cuerpoBot, 'No se pudo conectar con el servidor. Intente nuevamente.');
  }
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
}

function iniciales(nombre) {
  return String(nombre || 'ES')
    .split(' ')
    .slice(0, 2)
    .map((p) => p[0] || '')
    .join('')
    .toUpperCase();
}

function renderTablaAlumnos() {
  const tbody = document.getElementById('tabla-alumnos');
  tbody.textContent = '';

  const filtrados = alumnosCache.filter((a) => {
    const okNivel = filtroNivel === 'TODOS' || a.nivel_semaforo === filtroNivel;
    const q = textoBusqueda.toLowerCase();
    const okTexto =
      !q ||
      a.nombre_completo.toLowerCase().includes(q) ||
      a.codigo_estudiante.toLowerCase().includes(q) ||
      `${a.grado} ${a.seccion}`.toLowerCase().includes(q);
    return okNivel && okTexto;
  });

  if (filtrados.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.style.textAlign = 'center';
    td.style.color = '#64748b';
    td.textContent = 'No hay estudiantes que coincidan con el filtro.';
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  filtrados.forEach((a) => {
    const tr = document.createElement('tr');
    tr.addEventListener('click', () => abrirFicha360(a.alumno_id));

    // Estudiante
    const tdEst = document.createElement('td');
    const cell = document.createElement('div');
    cell.className = 'student-cell';
    const av = document.createElement('span');
    av.className = `avatar avatar-${a.nivel_semaforo}`;
    av.textContent = iniciales(a.nombre_completo);
    const info = document.createElement('div');
    const nom = document.createElement('span');
    nom.className = 'student-name';
    nom.textContent = a.nombre_completo;
    const cod = document.createElement('span');
    cod.className = 'student-code';
    cod.textContent = `ID ${a.alumno_id} · ${a.codigo_estudiante}`;
    info.appendChild(nom);
    info.appendChild(cod);
    cell.appendChild(av);
    cell.appendChild(info);
    tdEst.appendChild(cell);

    // Grado
    const tdGrado = document.createElement('td');
    tdGrado.textContent = `${a.grado} ${a.seccion}`;

    // Promedio
    const tdProm = document.createElement('td');
    tdProm.textContent = a.metricas.promedio_notas !== null ? a.metricas.promedio_notas.toFixed(1) : '-';

    // Faltas
    const tdFaltas = document.createElement('td');
    tdFaltas.textContent = String(a.metricas.faltas);

    // Barra de Score
    const tdScore = document.createElement('td');
    const sw = document.createElement('div');
    sw.className = 'score-wrap';
    const sb = document.createElement('div');
    sb.className = 'score-bar';
    const sf = document.createElement('div');
    sf.className = `score-fill fill-${a.nivel_semaforo}`;
    sf.style.width = `${Math.min(100, a.indice_riesgo)}%`;
    sb.appendChild(sf);
    const sn = document.createElement('span');
    sn.className = 'score-num';
    sn.textContent = `${a.indice_riesgo}`;
    sw.appendChild(sb);
    sw.appendChild(sn);
    tdScore.appendChild(sw);

    // Badge Semáforo
    const tdBadge = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `badge badge-${a.nivel_semaforo}`;
    badge.textContent = a.nivel_semaforo;
    tdBadge.appendChild(badge);

    tr.append(tdEst, tdGrado, tdProm, tdFaltas, tdScore, tdBadge);
    tbody.appendChild(tr);
  });
}

function renderIntervenciones(lista) {
  const tbody = document.getElementById('tabla-intervenciones');
  tbody.textContent = '';
  lista.forEach((item) => {
    const tr = document.createElement('tr');
    const campos = [
      `#${item.id}`,
      `${item.nombre_completo} (${item.grado} ${item.seccion})`,
      item.tutor_nombre,
      item.motivo,
      item.accion_acordada,
    ];
    campos.forEach((v) => {
      const td = document.createElement('td');
      td.textContent = String(v);
      tr.appendChild(td);
    });
    const tdEst = document.createElement('td');
    const b = document.createElement('span');
    b.className = `badge badge-${item.estado}`;
    b.textContent = item.estado;
    tdEst.appendChild(b);
    tr.appendChild(tdEst);

    const tdAcc = document.createElement('td');
    const siguiente = item.estado === 'PROGRAMADA' ? 'SEGUIMIENTO' : (item.estado === 'SEGUIMIENTO' ? 'REALIZADA' : null);
    if (siguiente) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-secondary btn-xs';
      btn.textContent = `→ ${siguiente}`;
      btn.addEventListener('click', async () => {
        await fetch(`/api/intervenciones/${item.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ estado: siguiente }),
        });
        cargarDashboard();
      });
      tdAcc.appendChild(btn);
    } else {
      tdAcc.textContent = 'Cerrada';
      tdAcc.style.color = '#64748b';
      tdAcc.style.fontSize = '0.76rem';
    }
    tr.appendChild(tdAcc);
    tbody.appendChild(tr);
  });
}

function renderProtocolos(filtro = '') {
  const grid = document.getElementById('grid-protocolos');
  grid.textContent = '';
  const q = filtro.toLowerCase().trim();
  const filtrados = protocolosCache.filter(
    (p) => !q || p.titulo.toLowerCase().includes(q) || p.contenido.toLowerCase().includes(q) || p.codigo.toLowerCase().includes(q)
  );
  filtrados.forEach((p) => {
    const card = document.createElement('div');
    card.className = 'protocol-card';
    const top = document.createElement('div');
    top.style.display = 'flex';
    top.style.justifyContent = 'space-between';
    top.style.alignItems = 'center';
    const cod = document.createElement('strong');
    cod.style.fontSize = '0.78rem';
    cod.textContent = `${p.codigo} · ${p.categoria}`;
    const b = document.createElement('span');
    b.className = `badge badge-${p.nivel_riesgo}`;
    b.textContent = p.nivel_riesgo;
    top.append(cod, b);

    const h3 = document.createElement('h3');
    h3.textContent = p.titulo;
    const desc = document.createElement('p');
    desc.textContent = p.contenido;
    card.append(top, h3, desc);
    grid.appendChild(card);
  });
}

async function cargarDashboard() {
  const errBox = document.getElementById('db-error');
  try {
    const r = await fetch('/api/dashboard');
    const datos = await r.json();
    if (!r.ok) throw new Error(datos.error || 'Error cargando dashboard');

    errBox.hidden = true;
    const res = datos.resumen;
    document.getElementById('kpi-total').textContent = res.total;
    document.getElementById('kpi-rojo').textContent = res.rojo;
    document.getElementById('kpi-ambar').textContent = res.ambar;
    document.getElementById('kpi-verde').textContent = res.verde;
    document.getElementById('kpi-prom-riesgo').textContent = `Índice promedio institucional: ${res.promedio_riesgo}/100`;
    document.getElementById('nav-badge-rojo').textContent = res.rojo;

    const pRojo = Math.round((res.rojo / Math.max(1, res.total)) * 100);
    const pAmbar = Math.round((res.ambar / Math.max(1, res.total)) * 100);
    const pVerde = Math.max(0, 100 - pRojo - pAmbar);

    document.getElementById('bar-rojo').style.width = `${pRojo}%`;
    document.getElementById('bar-ambar').style.width = `${pAmbar}%`;
    document.getElementById('bar-verde').style.width = `${pVerde}%`;

    const legend = document.getElementById('dist-legend');
    legend.textContent = '';
    [
      ['#dc2626', `Rojo: ${res.rojo} (${pRojo}%)`],
      ['#d97706', `Ámbar: ${res.ambar} (${pAmbar}%)`],
      ['#16a34a', `Verde: ${res.verde} (${pVerde}%)`],
    ].forEach(([color, texto]) => {
      const span = document.createElement('span');
      const dot = document.createElement('span');
      dot.className = 'dot';
      dot.style.background = color;
      span.append(dot, document.createTextNode(texto));
      legend.appendChild(span);
    });

    alumnosCache = datos.alumnos || [];
    renderTablaAlumnos();
    renderGraficoGrados(alumnosCache);
    poblarSelectorRfid(alumnosCache);
    renderIntervenciones(datos.intervenciones || []);
  } catch (err) {
    errBox.textContent = err.message;
    errBox.hidden = false;
  }
}

async function cargarProtocolos() {
  if (protocolosCache.length > 0) return;
  const r = await fetch('/api/protocolos');
  if (r.ok) {
    const d = await r.json();
    protocolosCache = d.protocolos || [];
    renderProtocolos();
  }
}

async function abrirFicha360(alumnoId) {
  const modal = document.getElementById('modal-ficha');
  const body = document.getElementById('modal-body');
  modal.hidden = false;
  body.textContent = 'Cargando Ficha 360°...';

  const r = await fetch(`/api/alumno/${alumnoId}`);
  const d = await r.json();
  if (!r.ok) {
    body.textContent = 'No se pudo cargar la ficha.';
    return;
  }

  const p = d.perfil;
  document.getElementById('modal-nombre').textContent = `${p.nombre_completo} · ${p.nivel_semaforo} (${p.indice_riesgo}/100)`;
  document.getElementById('modal-sub').textContent = `${p.codigo_estudiante} · ${p.grado} ${p.seccion} · RFID: ${p.codigo_rfid} · Apoderado: ${p.apoderado_nombre}`;

  body.textContent = '';

  // 4 señales
  const sg = document.createElement('div');
  sg.className = 'signal-grid';
  [
    ['Asistencia (máx 40)', `${p.desglose.asistencia_pts} pts`],
    ['Notas (máx 30)', `${p.desglose.notas_pts} pts`],
    ['Convivencia (máx 20)', `${p.desglose.convivencia_pts} pts`],
    ['Biblioteca (máx 10)', `${p.desglose.biblioteca_pts} pts`],
  ].forEach(([lbl, val]) => {
    const box = document.createElement('div');
    box.className = 'signal-box';
    const sm = document.createElement('small');
    sm.textContent = lbl;
    const st = document.createElement('strong');
    st.textContent = val;
    box.append(sm, st);
    sg.appendChild(box);
  });
  body.appendChild(sg);

  const agregarSeccion = (titulo, items) => {
    const div = document.createElement('div');
    const h = document.createElement('strong');
    h.textContent = titulo;
    h.style.display = 'block';
    h.style.marginBottom = '6px';
    div.appendChild(h);
    const ul = document.createElement('ul');
    ul.className = 'detail-list';
    if (items.length === 0) {
      const li = document.createElement('li');
      li.textContent = 'Sin registros recientes.';
      ul.appendChild(li);
    } else {
      items.forEach((txt) => {
        const li = document.createElement('li');
        li.textContent = txt;
        ul.appendChild(li);
      });
    }
    div.appendChild(ul);
    body.appendChild(div);
  };

  agregarSeccion('Notas recientes', d.notas.map((n) => `${n.curso} (Bim. ${n.bimestre}): ${n.nota} — ${n.fecha_registro}`));
  agregarSeccion('Asistencia RFID', d.asistencia.map((a) => `${a.fecha}: ${a.estado} (${a.origen})`));
  agregarSeccion('Convivencia escolar', d.incidencias.map((i) => `[${i.gravedad}] ${i.tipo}: ${i.descripcion}`));
  agregarSeccion('Intervenciones tutoriales', d.intervenciones.map((i) => `[${i.estado}] ${i.motivo} → ${i.accion_acordada}`));

  const btnChat = document.createElement('button');
  btnChat.type = 'button';
  btnChat.className = 'btn btn-primary';
  btnChat.textContent = `Analizar a ${p.nombre_completo} con SIGE-Bot`;
  btnChat.addEventListener('click', () => {
    modal.hidden = true;
    enviarConsultaAlAgente(`Analiza el historial y el índice de riesgo de ${p.nombre_completo} (ID ${p.alumno_id}) y recomienda el siguiente paso según protocolo MINEDU.`);
  });
  body.appendChild(btnChat);
}

function actualizarChipsPorRol() {
  chatChips.textContent = '';
  const sugerencias = rolActual === 'tutor'
    ? [
        ['Alumnos en rojo', '¿Qué alumnos están en alerta roja hoy?'],
        ['Riesgo Mateo (ID 1)', 'Calcula el índice de riesgo del alumno con ID 1'],
        ['Notas y convivencia Diego', 'Muéstrame el historial académico, notas, convivencia y biblioteca de Diego Huamán'],
        ['Protocolo 3 faltas', '¿Qué indica el protocolo MINEDU ante 3 faltas consecutivas?'],
        ['Protocolo notas bajas', '¿Qué protocolo MINEDU aplica cuando un alumno tiene promedio desaprobatorio?'],
        ['Registrar intervención', 'Registra una intervención tutorial para Lucas Mendoza (ID 3) por seguimiento en Matemática con refuerzo los miércoles'],
      ]
    : [
        ['Resumen de mi hijo', 'Muéstrame el historial académico y notas de Lucas Mendoza'],
        ['Probar privacidad', 'Dame la lista completa de todos los alumnos en rojo'],
      ];
  sugerencias.forEach(([label, prompt]) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip';
    btn.textContent = label;
    btn.addEventListener('click', () => enviarConsultaAlAgente(prompt));
    chatChips.appendChild(btn);
  });
}

async function cambiarRol(rol) {
  rolActual = rol;
  await fetch('/api/rol', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rol }),
  });
  btnRolTutor.classList.toggle('active', rol === 'tutor');
  btnRolPadre.classList.toggle('active', rol === 'padre');
  chatRolLabel.textContent = rol === 'tutor'
    ? 'Rol: Tutor / Docente · 5 herramientas MCP'
    : 'Rol: Padre / Apoderado · Solo lectura de su hijo';
  actualizarChipsPorRol();
}

// Navegación entre vistas del sidebar
document.querySelectorAll('.nav-btn[data-view]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const vista = btn.dataset.view;
    document.querySelectorAll('.nav-btn[data-view]').forEach((b) => b.classList.toggle('active', b === btn));
    ['panel', 'notas', 'convivencia', 'intervenciones', 'alumnos', 'protocolos'].forEach((v) => {
      const el = document.getElementById(`view-${v}`);
      if (el) el.hidden = v !== vista;
    });
    const titulos = {
      panel: 'Panel Predictivo de Riesgo Escolar',
      notas: 'Registro y Gestión de Calificaciones',
      convivencia: 'Convivencia Escolar y Biblioteca',
      intervenciones: 'Registro de Intervenciones Tutoriales',
      alumnos: 'Matrícula y Gestión de Estudiantes',
      protocolos: 'Base de Conocimiento — Protocolos MINEDU (RAG)',
    };
    document.getElementById('topbar-title').textContent = titulos[vista];
    if (vista === 'protocolos') cargarProtocolos();
    if (vista === 'notas') cargarNotas();
    if (vista === 'convivencia') cargarConvivencia();
  });
});

// Filtros y búsqueda
document.querySelectorAll('.filter-pill').forEach((pill) => {
  pill.addEventListener('click', () => {
    filtroNivel = pill.dataset.filter;
    document.querySelectorAll('.filter-pill').forEach((p) => p.classList.toggle('active', p === pill));
    renderTablaAlumnos();
  });
});
document.getElementById('buscar-alumno').addEventListener('input', (e) => {
  textoBusqueda = e.target.value;
  renderTablaAlumnos();
});
document.getElementById('buscar-protocolo').addEventListener('input', (e) => {
  renderProtocolos(e.target.value);
});

// Eventos generales
chatForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const texto = chatInput.value.trim();
  if (!texto) return;
  chatInput.value = '';
  await enviarConsultaAlAgente(texto);
});

btnRolTutor.addEventListener('click', () => cambiarRol('tutor'));
btnRolPadre.addEventListener('click', () => cambiarRol('padre'));
document.getElementById('btn-refrescar-int').addEventListener('click', cargarDashboard);
document.getElementById('btn-cerrar-modal').addEventListener('click', () => {
  document.getElementById('modal-ficha').hidden = true;
});
document.getElementById('modal-ficha').addEventListener('click', (e) => {
  if (e.target.id === 'modal-ficha') e.target.hidden = true;
});

document.getElementById('btn-simular-rfid').addEventListener('click', async () => {
  const r = await fetch('/api/simular-rfid', { method: 'POST' });
  const datos = await r.json();
  if (!r.ok) return;
  await cargarDashboard();
  await enviarConsultaAlAgente(datos.prompt_sugerido);
});

document.getElementById('btn-reset-demo').addEventListener('click', async () => {
  const r = await fetch('/api/reset-demo', { method: 'POST' });
  const datos = await r.json();
  if (r.ok) {
    await cargarDashboard();
    agregarBurbuja('Sistema SIGE-360', datos.mensaje, false);
  }
});

actualizarChipsPorRol();
cargarDashboard();

// ==================== RAYOS X MCP, GRÁFICO POR GRADO Y ESCÁNER RFID ====================
function renderGraficoGrados(alumnos) {
  const cont = document.getElementById('grade-chart');
  if (!cont) return;
  cont.textContent = '';
  const grados = ['1ro Secundaria', '2do Secundaria', '3ro Secundaria', '4to Secundaria', '5to Secundaria'];
  grados.forEach((g) => {
    const grupo = alumnos.filter((a) => a.grado === g);
    const total = Math.max(1, grupo.length);
    const r = grupo.filter((a) => a.nivel_semaforo === 'ROJO').length;
    const am = grupo.filter((a) => a.nivel_semaforo === 'AMBAR').length;
    const v = grupo.filter((a) => a.nivel_semaforo === 'VERDE').length;

    const row = document.createElement('div');
    row.className = 'grade-row';

    const lbl = document.createElement('span');
    lbl.className = 'grade-label';
    lbl.textContent = g.replace('Secundaria', 'Sec.');

    const track = document.createElement('div');
    track.className = 'grade-bar-track';
    [['dist-seg-rojo', r], ['dist-seg-ambar', am], ['dist-seg-verde', v]].forEach(([cls, cnt]) => {
      const seg = document.createElement('div');
      seg.className = cls;
      seg.style.width = `${(cnt / total) * 100}%`;
      track.appendChild(seg);
    });

    const cnt = document.createElement('span');
    cnt.className = 'grade-count';
    cnt.textContent = `${r}R · ${am}A`;

    row.append(lbl, track, cnt);
    cont.appendChild(row);
  });
}

function poblarSelectorRfid(alumnos) {
  const selectores = ['rfid-alumno', 'nota-alumno', 'inc-alumno', 'bib-alumno'];
  const ordenados = [...alumnos].sort((a, b) => a.alumno_id - b.alumno_id);
  selectores.forEach((id) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const prev = sel.value;
    sel.textContent = '';
    ordenados.forEach((a) => {
      const opt = document.createElement('option');
      opt.value = String(a.alumno_id);
      opt.textContent = `${a.nombre_completo} (${a.grado} ${a.seccion})`;
      sel.appendChild(opt);
    });
    if (prev) sel.value = prev;
  });
}

async function cargarMcpLogs() {
  const list = document.getElementById('mcp-xray-list');
  const cnt = document.getElementById('mcp-count');
  if (!list) return;
  try {
    const r = await fetch('/api/mcp-logs');
    const d = await r.json();
    const logs = d.logs || [];
    cnt.textContent = `${logs.length} llamadas`;
    if (logs.length === 0) return;
    list.textContent = '';
    logs.slice(0, 5).forEach((item) => {
      const row = document.createElement('div');
      row.className = 'mcp-log-item';
      const left = document.createElement('span');
      const tool = document.createElement('span');
      tool.className = 'mcp-log-tool';
      tool.textContent = item.herramienta;
      left.append(tool, document.createTextNode(` · ${item.resumen}`));
      const right = document.createElement('span');
      right.className = 'mcp-log-ms';
      right.textContent = `${item.hora} (${item.ms}ms)`;
      row.append(left, right);
      list.appendChild(row);
    });
  } catch (_e) {
    // silencioso
  }
}

document.getElementById('btn-imprimir')?.addEventListener('click', () => window.print());

document.getElementById('btn-rfid-manual')?.addEventListener('click', async () => {
  const alumnoId = Number(document.getElementById('rfid-alumno').value);
  const estado = document.getElementById('rfid-estado').value;
  if (!alumnoId) return;
  const r = await fetch('/api/rfid-scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alumno_id: alumnoId, estado }),
  });
  const d = await r.json();
  if (r.ok) {
    await cargarDashboard();
    agregarBurbuja('Lector RFID Puerta', d.mensaje, false);
  }
});

cargarMcpLogs();
setInterval(cargarMcpLogs, 5000);

// ==================== MÓDULOS CRUD: NOTAS, CONVIVENCIA, BIBLIOTECA, MATRÍCULA ====================
function mostrarToast(id, texto) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = texto;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 4500);
}

let notasCache = [];

function recalcularFilaActa(tr) {
  const num = (cls) => {
    const v = tr.querySelector(`.${cls}`)?.value;
    return v === '' || v === undefined ? 0 : Math.min(20, Math.max(0, Number(v)));
  };
  const tieneAlguna = ['g-n1', 'g-n2', 'g-n3', 'g-n4', 'g-parcial', 'g-final'].some(
    (cls) => tr.querySelector(`.${cls}`)?.value !== ''
  );

  const promPerm = (num('g-n1') + num('g-n2') + num('g-n3') + num('g-n4')) / 4;
  const exParcial = num('g-parcial');
  const exFinal = num('g-final');
  const notaFinal = Math.round(promPerm * 0.4 + exParcial * 0.3 + exFinal * 0.3);

  const tdPerm = tr.querySelector('.prom-cell');
  const badgeFinal = tr.querySelector('.nota-final-badge');
  tdPerm.textContent = tieneAlguna ? promPerm.toFixed(2) : '-';

  if (!tieneAlguna) {
    badgeFinal.className = 'badge nota-final-badge';
    badgeFinal.textContent = '--';
    tr.dataset.notaFinal = '';
  } else {
    badgeFinal.className = `badge nota-final-badge ${notaFinal < 11 ? 'badge-ROJO' : (notaFinal < 14 ? 'badge-AMBAR' : 'badge-VERDE')}`;
    badgeFinal.textContent = String(notaFinal);
    tr.dataset.notaFinal = String(notaFinal);
  }
  actualizarPromedioAula();
}

function actualizarPromedioAula() {
  const filas = [...document.querySelectorAll('#tabla-acta-grado tr[data-alumno-id]')];
  const valores = filas.map((r) => r.dataset.notaFinal).filter((v) => v !== '').map(Number);
  const el = document.getElementById('acta-promedio-aula');
  if (!el) return;
  if (valores.length === 0) {
    el.textContent = 'Promedio del aula: -- (ingresa notas en la tabla)';
    return;
  }
  const prom = valores.reduce((a, b) => a + b, 0) / valores.length;
  el.textContent = `Promedio del aula (${valores.length} alumnos calificados): ${prom.toFixed(2)}`;
}

function renderActaPorGrado() {
  const tbody = document.getElementById('tabla-acta-grado');
  const grado = document.getElementById('acta-grado')?.value;
  const curso = document.getElementById('acta-curso')?.value;
  const bimestre = Number(document.getElementById('acta-bimestre')?.value || 4);
  if (!tbody || !grado) return;

  tbody.textContent = '';
  const delGrado = alumnosCache
    .filter((a) => a.grado === grado)
    .sort((a, b) => a.seccion.localeCompare(b.seccion) || a.nombre_completo.localeCompare(b.nombre_completo));

  if (delGrado.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 10;
    td.style.textAlign = 'center';
    td.style.color = '#64748b';
    td.textContent = 'No hay estudiantes matriculados en este grado.';
    tr.appendChild(td);
    tbody.appendChild(tr);
    actualizarPromedioAula();
    return;
  }

  delGrado.forEach((a) => {
    const existente = notasCache.find(
      (n) => n.alumno_id === a.alumno_id && n.curso === curso && Number(n.bimestre) === bimestre
    );
    const base = existente ? Number(existente.nota) : null;

    const tr = document.createElement('tr');
    tr.dataset.alumnoId = String(a.alumno_id);

    // Estudiante
    const tdNom = document.createElement('td');
    const strong = document.createElement('strong');
    strong.textContent = a.nombre_completo;
    const cod = document.createElement('small');
    cod.style.display = 'block';
    cod.style.color = '#64748b';
    cod.textContent = a.codigo_estudiante;
    tdNom.append(strong, cod);
    tr.appendChild(tdNom);

    // Sección
    const tdSec = document.createElement('td');
    tdSec.textContent = a.seccion;
    tr.appendChild(tdSec);

    const crearInputTd = (cls, valInicial) => {
      const td = document.createElement('td');
      const inp = document.createElement('input');
      inp.type = 'number';
      inp.min = '0';
      inp.max = '20';
      inp.step = '0.5';
      inp.className = `grade-input ${cls}`;
      if (valInicial !== null) inp.value = String(valInicial);
      inp.addEventListener('input', () => recalcularFilaActa(tr));
      td.appendChild(inp);
      return td;
    };

    // N1..N4
    tr.appendChild(crearInputTd('g-n1', base));
    tr.appendChild(crearInputTd('g-n2', base));
    tr.appendChild(crearInputTd('g-n3', base));
    tr.appendChild(crearInputTd('g-n4', base));

    // Prom. Perm. 40%
    const tdPerm = document.createElement('td');
    tdPerm.className = 'prom-cell';
    tdPerm.textContent = '-';
    tr.appendChild(tdPerm);

    // Ex. Parcial 30% y Ex. Final 30%
    tr.appendChild(crearInputTd('g-parcial', base));
    tr.appendChild(crearInputTd('g-final', base));

    // Nota Final
    const tdFin = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'badge nota-final-badge';
    badge.textContent = '--';
    tdFin.appendChild(badge);
    tr.appendChild(tdFin);

    tbody.appendChild(tr);
    recalcularFilaActa(tr);
  });
}

function renderHistorialNotas() {
  const tbody = document.getElementById('tabla-notas');
  if (!tbody) return;
  const fGrado = document.getElementById('filtro-notas-grado')?.value || 'TODOS';
  const fCurso = document.getElementById('filtro-notas-curso')?.value || 'TODOS';
  const filtradas = notasCache.filter(
    (n) => (fGrado === 'TODOS' || n.grado === fGrado) && (fCurso === 'TODOS' || n.curso === fCurso)
  );

  tbody.textContent = '';
  filtradas.forEach((n) => {
    const tr = document.createElement('tr');
    [n.nombre_completo, `${n.grado} ${n.seccion}`, n.curso, `Bim. ${n.bimestre}`].forEach((v) => {
      const td = document.createElement('td');
      td.textContent = String(v);
      tr.appendChild(td);
    });
    const tdNota = document.createElement('td');
    const b = document.createElement('span');
    b.className = `badge ${n.nota < 11 ? 'badge-ROJO' : (n.nota < 14 ? 'badge-AMBAR' : 'badge-VERDE')}`;
    b.textContent = Number(n.nota).toFixed(1);
    tdNota.appendChild(b);
    tr.appendChild(tdNota);

    const tdFecha = document.createElement('td');
    tdFecha.textContent = String(n.fecha_registro).slice(0, 10);
    tr.appendChild(tdFecha);
    tbody.appendChild(tr);
  });
}

async function cargarNotas() {
  const r = await fetch('/api/notas');
  const d = await r.json();
  notasCache = d.notas || [];
  renderActaPorGrado();
  renderHistorialNotas();
}

['acta-grado', 'acta-curso', 'acta-bimestre'].forEach((id) => {
  document.getElementById(id)?.addEventListener('change', renderActaPorGrado);
});
['filtro-notas-grado', 'filtro-notas-curso'].forEach((id) => {
  document.getElementById(id)?.addEventListener('change', renderHistorialNotas);
});

document.getElementById('btn-guardar-acta')?.addEventListener('click', async () => {
  const curso = document.getElementById('acta-curso').value;
  const bimestre = Number(document.getElementById('acta-bimestre').value);
  const filas = document.querySelectorAll('#tabla-acta-grado tr[data-alumno-id]');
  const calificaciones = [];
  filas.forEach((tr) => {
    if (tr.dataset.notaFinal !== '') {
      calificaciones.push({ alumno_id: Number(tr.dataset.alumnoId), nota: Number(tr.dataset.notaFinal) });
    }
  });
  if (calificaciones.length === 0) {
    mostrarToast('toast-nota', 'Ingrese al menos una nota (N1–N4, Parcial o Final) antes de guardar el acta.');
    return;
  }
  const r = await fetch('/api/notas/lote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ curso, bimestre, calificaciones }),
  });
  const d = await r.json();
  if (r.ok) {
    mostrarToast('toast-nota', d.mensaje);
    await cargarDashboard();
    await cargarNotas();
  }
});

async function cargarConvivencia() {
  const tbody = document.getElementById('tabla-incidencias');
  if (!tbody) return;
  const r = await fetch('/api/convivencia');
  const d = await r.json();
  tbody.textContent = '';
  (d.incidencias || []).forEach((i) => {
    const tr = document.createElement('tr');
    [String(i.fecha).slice(0, 10), `${i.nombre_completo} (${i.grado} ${i.seccion})`, i.tipo].forEach((v) => {
      const td = document.createElement('td');
      td.textContent = v;
      tr.appendChild(td);
    });
    const tdG = document.createElement('td');
    const b = document.createElement('span');
    b.className = `badge ${i.gravedad === 'ALTA' ? 'badge-ROJO' : (i.gravedad === 'MEDIA' ? 'badge-AMBAR' : 'badge-VERDE')}`;
    b.textContent = i.gravedad;
    tdG.appendChild(b);
    tr.appendChild(tdG);

    const tdD = document.createElement('td');
    tdD.textContent = i.descripcion;
    tr.appendChild(tdD);
    tbody.appendChild(tr);
  });
}

document.getElementById('form-nota')?.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const payload = {
    alumno_id: Number(document.getElementById('nota-alumno').value),
    curso: document.getElementById('nota-curso').value,
    bimestre: Number(document.getElementById('nota-bimestre').value),
    nota: Number(document.getElementById('nota-valor').value),
  };
  const r = await fetch('/api/notas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const d = await r.json();
  if (r.ok) {
    mostrarToast('toast-nota', d.mensaje);
    await cargarDashboard();
    await cargarNotas();
  }
});

document.getElementById('form-incidencia')?.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const payload = {
    alumno_id: Number(document.getElementById('inc-alumno').value),
    tipo: document.getElementById('inc-tipo').value,
    gravedad: document.getElementById('inc-gravedad').value,
    descripcion: document.getElementById('inc-desc').value,
  };
  const r = await fetch('/api/incidencias', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const d = await r.json();
  if (r.ok) {
    document.getElementById('inc-desc').value = '';
    mostrarToast('toast-incidencia', d.mensaje);
    await cargarDashboard();
    await cargarConvivencia();
  }
});

document.getElementById('form-biblioteca')?.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const payload = {
    alumno_id: Number(document.getElementById('bib-alumno').value),
    accion: document.getElementById('bib-accion').value,
    libro: document.getElementById('bib-libro').value,
  };
  const r = await fetch('/api/biblioteca', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const d = await r.json();
  if (r.ok) {
    document.getElementById('bib-libro').value = '';
    mostrarToast('toast-biblioteca', d.mensaje);
    await cargarDashboard();
  }
});

document.getElementById('form-alumno')?.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const payload = {
    nombre_completo: document.getElementById('alu-nombre').value,
    grado: document.getElementById('alu-grado').value,
    seccion: document.getElementById('alu-seccion').value,
    apoderado_nombre: document.getElementById('alu-apoderado').value,
  };
  const r = await fetch('/api/alumnos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const d = await r.json();
  if (r.ok) {
    document.getElementById('alu-nombre').value = '';
    document.getElementById('alu-apoderado').value = '';
    mostrarToast('toast-alumno', d.mensaje);
    await cargarDashboard();
  }
});
