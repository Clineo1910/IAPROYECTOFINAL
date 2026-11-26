let alumnosCache = [];

function iniciales(nombre) {
  return String(nombre || 'ES').split(' ').slice(0, 2).map((p) => p[0] || '').join('').toUpperCase();
}

function renderPrioritarios(alumnos) {
  const cont = document.getElementById('lista-prioritarios');
  cont.textContent = '';
  const criticos = alumnos.filter((a) => a.nivel_semaforo !== 'VERDE').slice(0, 5);

  if (criticos.length === 0) {
    const p = document.createElement('p');
    p.style.color = '#64748b';
    p.textContent = 'Excelente: no hay estudiantes en alerta roja o ámbar hoy.';
    cont.appendChild(p);
    return;
  }

  criticos.forEach((a) => {
    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.flexWrap = 'wrap';
    row.style.justifyContent = 'space-between';
    row.style.alignItems = 'center';
    row.style.gap = '12px';
    row.style.padding = '12px 14px';
    row.style.borderRadius = '12px';
    row.style.border = a.nivel_semaforo === 'ROJO' ? '1px solid #fecaca' : '1px solid #fde68a';
    row.style.background = a.nivel_semaforo === 'ROJO' ? '#fef2f2' : '#fffbeb';

    const left = document.createElement('div');
    left.className = 'student-cell';
    const av = document.createElement('span');
    av.className = `avatar avatar-${a.nivel_semaforo}`;
    av.textContent = iniciales(a.nombre_completo);
    const info = document.createElement('div');
    const nom = document.createElement('span');
    nom.className = 'student-name';
    nom.textContent = `${a.nombre_completo} · ${a.grado} ${a.seccion}`;
    const det = document.createElement('span');
    det.className = 'student-code';
    det.textContent = `Promedio: ${a.metricas.promedio_notas ?? '-'} · Faltas: ${a.metricas.faltas} · Incidencias altas: ${a.metricas.incidencias_alta || 0}`;
    info.append(nom, det);
    left.append(av, info);

    const right = document.createElement('div');
    right.style.display = 'flex';
    right.style.alignItems = 'center';
    right.style.gap = '10px';
    const badge = document.createElement('span');
    badge.className = `badge badge-${a.nivel_semaforo}`;
    badge.textContent = `${a.nivel_semaforo} · ${a.indice_riesgo}/100`;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-secondary btn-xs';
    btn.textContent = 'Ver Ficha 360°';
    btn.addEventListener('click', () => abrirFicha360(a.alumno_id));
    right.append(badge, btn);

    row.append(left, right);
    cont.appendChild(row);
  });
}

function renderResumenGrados(alumnos) {
  const tbody = document.getElementById('tabla-resumen-grados');
  tbody.textContent = '';
  ['1ro Secundaria', '2do Secundaria', '3ro Secundaria', '4to Secundaria', '5to Secundaria'].forEach((g) => {
    const grupo = alumnos.filter((a) => a.grado === g);
    const rojos = grupo.filter((a) => a.nivel_semaforo === 'ROJO').length;
    const ambars = grupo.filter((a) => a.nivel_semaforo === 'AMBAR').length;
    const verdes = grupo.filter((a) => a.nivel_semaforo === 'VERDE').length;
    const notasValidas = grupo.map((a) => a.metricas.promedio_notas).filter((v) => v !== null);
    const prom = notasValidas.length ? (notasValidas.reduce((x, y) => x + y, 0) / notasValidas.length).toFixed(1) : '-';

    const tr = document.createElement('tr');
    const tdG = document.createElement('td'); tdG.style.fontWeight = '600'; tdG.textContent = g;
    const tdT = document.createElement('td'); tdT.textContent = String(grupo.length);

    const mkBadgeTd = (num, cls) => {
      const td = document.createElement('td');
      const sp = document.createElement('span');
      sp.className = `badge ${cls}`;
      sp.textContent = String(num);
      td.appendChild(sp);
      return td;
    };

    const tdP = document.createElement('td'); tdP.style.fontWeight = '700'; tdP.textContent = String(prom);

    tr.append(
      tdG,
      tdT,
      mkBadgeTd(rojos, rojos > 0 ? 'badge-ROJO' : 'badge-GENERAL'),
      mkBadgeTd(ambars, ambars > 0 ? 'badge-AMBAR' : 'badge-GENERAL'),
      mkBadgeTd(verdes, 'badge-VERDE'),
      tdP
    );
    tbody.appendChild(tr);
  });
}

function poblarSelectores(alumnos) {
  const ordenados = [...alumnos].sort((a, b) => a.alumno_id - b.alumno_id);
  const selRfid = document.getElementById('rfid-alumno');
  if (selRfid && selRfid.options.length === 0) {
    ordenados.forEach((a) => {
      const opt = document.createElement('option');
      opt.value = String(a.alumno_id);
      opt.textContent = `${a.nombre_completo} (${a.codigo_rfid})`;
      selRfid.appendChild(opt);
    });
    window.SIGE.hacerBuscable('rfid-alumno', 'Filtrar alumno RFID...');
  }
  const selBusc = document.getElementById('buscador-rapido');
  if (selBusc && selBusc.options.length <= 1) {
    ordenados.forEach((a) => {
      const opt = document.createElement('option');
      opt.value = String(a.alumno_id);
      opt.textContent = `${a.nombre_completo} (${a.grado} ${a.seccion})`;
      selBusc.appendChild(opt);
    });
    window.SIGE.hacerBuscable('buscador-rapido', 'Buscar Ficha 360°...');
  }
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
    document.getElementById('kpi-prom-riesgo').textContent = `Índice promedio: ${res.promedio_riesgo}/100`;

    alumnosCache = datos.alumnos || [];
    renderPrioritarios(alumnosCache);
    renderResumenGrados(alumnosCache);
    poblarSelectores(alumnosCache);
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

  agregarSeccion('Notas recientes', d.notas.slice(0, 6).map((n) => `${n.curso} (Bim. ${n.bimestre}): ${n.nota}`));
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

document.getElementById('buscador-rapido').addEventListener('change', (e) => {
  if (e.target.value) {
    abrirFicha360(Number(e.target.value));
    e.target.value = '';
  }
});
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
window.SIGE.iniciarLayout({ paginaActiva: 'panel', titulo: 'Panel Ejecutivo de Riesgo Escolar' }).then(cargarDashboard);
