let alumnosCache = [];
let filtroNivel = 'TODOS';
let textoBusqueda = '';

function iniciales(nombre) {
  return String(nombre || 'ES').split(' ').slice(0, 2).map((p) => p[0] || '').join('').toUpperCase();
}

function renderTablaAlumnos() {
  const tbody = document.getElementById('tabla-alumnos');
  tbody.textContent = '';
  const filtrados = alumnosCache.filter((a) => {
    const okNivel = filtroNivel === 'TODOS' || a.nivel_semaforo === filtroNivel;
    const q = textoBusqueda.toLowerCase();
    const okTexto = !q || a.nombre_completo.toLowerCase().includes(q) || a.codigo_estudiante.toLowerCase().includes(q) || `${a.grado} ${a.seccion}`.toLowerCase().includes(q);
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
    info.append(nom, cod);
    cell.append(av, info);
    tdEst.appendChild(cell);

    const tdGrado = document.createElement('td');
    tdGrado.textContent = `${a.grado} ${a.seccion}`;
    const tdProm = document.createElement('td');
    tdProm.textContent = a.metricas.promedio_notas !== null ? a.metricas.promedio_notas.toFixed(1) : '-';
    const tdFaltas = document.createElement('td');
    tdFaltas.textContent = String(a.metricas.faltas);

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
    sw.append(sb, sn);
    tdScore.appendChild(sw);

    const tdBadge = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = `badge badge-${a.nivel_semaforo}`;
    badge.textContent = a.nivel_semaforo;
    tdBadge.appendChild(badge);

    tr.append(tdEst, tdGrado, tdProm, tdFaltas, tdScore, tdBadge);
    tbody.appendChild(tr);
  });
}

function renderGraficoGrados(alumnos) {
  const cont = document.getElementById('grade-chart');
  cont.textContent = '';
  ['1ro Secundaria', '2do Secundaria', '3ro Secundaria', '4to Secundaria', '5to Secundaria'].forEach((g) => {
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
  [...alumnos].sort((a, b) => a.alumno_id - b.alumno_id).forEach((a) => {
    const opt = document.createElement('option');
    opt.value = String(a.alumno_id);
    opt.textContent = `${a.nombre_completo} (${a.codigo_rfid})`;
    sel.appendChild(opt);
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

    const pRojo = Math.round((res.rojo / Math.max(1, res.total)) * 100);
    const pAmbar = Math.round((res.ambar / Math.max(1, res.total)) * 100);
    const pVerde = Math.max(0, 100 - pRojo - pAmbar);
    document.getElementById('bar-rojo').style.width = `${pRojo}%`;
    document.getElementById('bar-ambar').style.width = `${pAmbar}%`;
    document.getElementById('bar-verde').style.width = `${pVerde}%`;

    const legend = document.getElementById('dist-legend');
    legend.textContent = '';
    [['#dc2626', `Rojo: ${res.rojo} (${pRojo}%)`], ['#d97706', `Ámbar: ${res.ambar} (${pAmbar}%)`], ['#16a34a', `Verde: ${res.verde} (${pVerde}%)`]].forEach(([color, texto]) => {
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
  } catch (err) {
    errBox.textContent = err.message;
    errBox.hidden = false;
  }
}

async function abrirFicha360(alumnoId) {
  const modal = document.getElementById('modal-ficha');
  const body = document.getElementById('modal-body');
  modal.hidden = false;
  body.textContent = 'Cargando Ficha 360°...';

  const r = await fetch(`/api/alumno/${alumnoId}`);
  const d = await r.json();
  if (!r.ok) { body.textContent = 'No se pudo cargar la ficha.'; return; }

  const p = d.perfil;
  document.getElementById('modal-nombre').textContent = `${p.nombre_completo} · ${p.nivel_semaforo} (${p.indice_riesgo}/100)`;
  document.getElementById('modal-sub').textContent = `${p.codigo_estudiante} · ${p.grado} ${p.seccion} · RFID: ${p.codigo_rfid} · Apoderado: ${p.apoderado_nombre}`;
  body.textContent = '';

  const sg = document.createElement('div');
  sg.className = 'signal-grid';
  [['Asistencia (/40)', `${p.desglose.asistencia_pts} pts`], ['Notas (/30)', `${p.desglose.notas_pts} pts`], ['Convivencia (/20)', `${p.desglose.convivencia_pts} pts`], ['Biblioteca (/10)', `${p.desglose.biblioteca_pts} pts`]].forEach(([lbl, val]) => {
    const box = document.createElement('div');
    box.className = 'signal-box';
    const sm = document.createElement('small'); sm.textContent = lbl;
    const st = document.createElement('strong'); st.textContent = val;
    box.append(sm, st);
    sg.appendChild(box);
  });
  body.appendChild(sg);

  const agregarSeccion = (titulo, items) => {
    const div = document.createElement('div');
    const h = document.createElement('strong'); h.textContent = titulo; h.style.display = 'block'; h.style.marginBottom = '6px';
    div.appendChild(h);
    const ul = document.createElement('ul'); ul.className = 'detail-list';
    (items.length ? items : ['Sin registros recientes.']).forEach((txt) => {
      const li = document.createElement('li'); li.textContent = txt; ul.appendChild(li);
    });
    div.appendChild(ul);
    body.appendChild(div);
  };

  agregarSeccion('Notas recientes', d.notas.map((n) => `${n.curso} (Bim. ${n.bimestre}): ${n.nota}`));
  agregarSeccion('Asistencia RFID', d.asistencia.map((a) => `${a.fecha}: ${a.estado} (${a.origen})`));
  agregarSeccion('Convivencia escolar', d.incidencias.map((i) => `[${i.gravedad}] ${i.tipo}: ${i.descripcion}`));
  agregarSeccion('Intervenciones tutoriales', d.intervenciones.map((i) => `[${i.estado}] ${i.motivo} → ${i.accion_acordada}`));

  const btnChat = document.createElement('button');
  btnChat.type = 'button';
  btnChat.className = 'btn btn-primary';
  btnChat.textContent = `Analizar a ${p.nombre_completo} con SIGE-Bot`;
  btnChat.addEventListener('click', () => {
    modal.hidden = true;
    window.SIGE.enviarConsultaAlAgente(`Analiza el historial y el índice de riesgo de ${p.nombre_completo} (ID ${p.alumno_id}) y recomienda el siguiente paso según protocolo MINEDU.`);
  });
  body.appendChild(btnChat);
}

document.querySelectorAll('.filter-pill').forEach((pill) => {
  pill.addEventListener('click', () => {
    filtroNivel = pill.dataset.filter;
    document.querySelectorAll('.filter-pill').forEach((p) => p.classList.toggle('active', p === pill));
    renderTablaAlumnos();
  });
});
document.getElementById('buscar-alumno').addEventListener('input', (e) => { textoBusqueda = e.target.value; renderTablaAlumnos(); });
document.getElementById('btn-cerrar-modal').addEventListener('click', () => { document.getElementById('modal-ficha').hidden = true; });
document.getElementById('modal-ficha').addEventListener('click', (e) => { if (e.target.id === 'modal-ficha') e.target.hidden = true; });

document.getElementById('btn-simular-rfid').addEventListener('click', async () => {
  const r = await fetch('/api/simular-rfid', { method: 'POST' });
  const datos = await r.json();
  if (!r.ok) return;
  await cargarDashboard();
  await window.SIGE.enviarConsultaAlAgente(datos.prompt_sugerido);
});

document.getElementById('btn-reset-demo').addEventListener('click', async () => {
  const r = await fetch('/api/reset-demo', { method: 'POST' });
  const datos = await r.json();
  if (r.ok) {
    await cargarDashboard();
    window.SIGE.agregarBurbuja('Sistema SIGE-360', datos.mensaje, false, false);
  }
});

document.getElementById('btn-rfid-manual').addEventListener('click', async () => {
  const alumnoId = Number(document.getElementById('rfid-alumno').value);
  const estado = document.getElementById('rfid-estado').value;
  if (!alumnoId) return;
  const r = await fetch('/api/rfid-scan', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alumno_id: alumnoId, estado }),
  });
  const d = await r.json();
  if (r.ok) {
    await cargarDashboard();
    window.SIGE.agregarBurbuja('Lector RFID Puerta', d.mensaje, false, false);
  }
});

window.onChatCompleted = cargarDashboard;
window.SIGE.iniciarLayout({ paginaActiva: 'panel', titulo: 'Panel Predictivo de Riesgo Escolar' }).then(cargarDashboard);
