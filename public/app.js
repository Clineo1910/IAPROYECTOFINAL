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
        ['Protocolo 3 faltas', '¿Qué indica el protocolo MINEDU ante 3 faltas consecutivas?'],
        ['Registrar intervención', 'Registra una intervención tutorial para Lucas Mendoza (ID 3) por seguimiento en Matemática con refuerzo los miércoles'],
      ]
    : [
        ['Resumen de mi hijo', 'Muéstrame el historial académico de Lucas Mendoza'],
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
    ['panel', 'intervenciones', 'protocolos'].forEach((v) => {
      document.getElementById(`view-${v}`).hidden = v !== vista;
    });
    const titulos = {
      panel: 'Panel Predictivo de Riesgo Escolar',
      intervenciones: 'Registro de Intervenciones Tutoriales',
      protocolos: 'Base de Conocimiento — Protocolos MINEDU (RAG)',
    };
    document.getElementById('topbar-title').textContent = titulos[vista];
    if (vista === 'protocolos') cargarProtocolos();
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
  const sel = document.getElementById('rfid-alumno');
  if (!sel || sel.options.length > 0) return;
  const ordenados = [...alumnos].sort((a, b) => a.alumno_id - b.alumno_id);
  ordenados.forEach((a) => {
    const opt = document.createElement('option');
    opt.value = String(a.alumno_id);
    opt.textContent = `${a.nombre_completo} (${a.codigo_rfid})`;
    sel.appendChild(opt);
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
