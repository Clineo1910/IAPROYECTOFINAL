const mensajesEl = document.getElementById('chat-mensajes');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-texto');

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
  wrap.append(meta, body);
  mensajesEl.appendChild(wrap);
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
  return body;
}

async function enviarConsulta(texto) {
  agregarBurbuja('Apoderado', texto, true);
  const cuerpo = agregarBurbuja('SIGE-Bot · Consultando', 'Verificando datos autorizados...', false);
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensaje: texto }),
    });
    if (r.status === 401) {
      window.location.href = '/login.html';
      return;
    }
    const d = await r.json();
    cuerpo.previousSibling.textContent = 'SIGE-Bot · Respuesta verificada';
    renderTextoSeguro(cuerpo, d.respuesta);
  } catch (_e) {
    renderTextoSeguro(cuerpo, 'No se pudo conectar con el asistente.');
  }
  mensajesEl.scrollTop = mensajesEl.scrollHeight;
}

async function cargarPortalPadre() {
  const r = await fetch('/api/mi-hijo');
  if (r.status === 401) {
    window.location.href = '/login.html';
    return;
  }
  const d = await r.json();
  const a = d.alumno;

  document.getElementById('padre-bienvenida').textContent = `Bienvenida, ${d.apoderado} · Acceso familiar seguro`;
  document.getElementById('hijo-nombre').textContent = a.nombre_completo;
  document.getElementById('hijo-meta').textContent = `${a.codigo_estudiante} · ${a.grado} Sección ${a.seccion}`;
  document.getElementById('hijo-promedio').textContent = a.promedio_notas !== null ? a.promedio_notas.toFixed(1) : '--';
  document.getElementById('hijo-faltas').textContent = String(a.faltas);
  document.getElementById('hijo-tardanzas').textContent = String(a.tardanzas);

  const chipResumen = document.getElementById('chip-resumen-hijo');
  if (chipResumen && a.nombre_completo) {
    chipResumen.dataset.prompt = `¿Cómo van las notas y la asistencia de mi hijo ${a.nombre_completo}?`;
  }

  const badge = document.getElementById('hijo-estado-badge');
  badge.className = `badge badge-${a.nivel_semaforo}`;
  badge.textContent = a.nivel_semaforo === 'ROJO'
    ? 'Requiere apoyo prioritario'
    : (a.nivel_semaforo === 'AMBAR' ? 'En seguimiento preventivo' : 'Desempeño estable');

  const tbNotas = document.getElementById('tabla-notas-hijo');
  tbNotas.textContent = '';
  const porCurso = new Map();
  (d.notas || []).forEach((n) => {
    if (!porCurso.has(n.curso)) {
      porCurso.set(n.curso, { 1: null, 2: null, 3: null, 4: null });
    }
    const bim = Number(n.bimestre);
    const reg = porCurso.get(n.curso);
    if (bim >= 1 && bim <= 4 && reg[bim] === null) {
      reg[bim] = Number(n.nota);
    }
  });

  const cursosOrdenados = Array.from(porCurso.keys()).sort((x, y) => x.localeCompare(y, 'es'));
  const sumBim = { 1: [], 2: [], 3: [], 4: [] };

  const crearCeldaNota = (val, destacado = false) => {
    const td = document.createElement('td');
    td.style.textAlign = 'center';
    if (val === null || Number.isNaN(val)) {
      td.style.color = '#94a3b8';
      td.textContent = '—';
      return td;
    }
    const bn = document.createElement('span');
    bn.className = `badge ${val < 11 ? 'badge-ROJO' : (val < 14 ? 'badge-AMBAR' : 'badge-VERDE')}`;
    if (destacado) bn.style.fontWeight = '700';
    bn.textContent = val.toFixed(1);
    td.appendChild(bn);
    return td;
  };

  cursosOrdenados.forEach((curso) => {
    const reg = porCurso.get(curso);
    const tr = document.createElement('tr');
    const tdC = document.createElement('td');
    tdC.style.fontWeight = '600';
    tdC.textContent = curso;
    tr.appendChild(tdC);

    const vals = [];
    [1, 2, 3, 4].forEach((b) => {
      const v = reg[b];
      if (v !== null) {
        vals.push(v);
        sumBim[b].push(v);
      }
      tr.appendChild(crearCeldaNota(v));
    });

    const prom = vals.length ? (vals.reduce((acc, x) => acc + x, 0) / vals.length) : null;
    tr.appendChild(crearCeldaNota(prom, true));

    const tdDes = document.createElement('td');
    if (prom === null) {
      tdDes.textContent = 'Sin notas';
    } else {
      tdDes.textContent = prom >= 14 ? 'Logro esperado' : (prom >= 11 ? 'En proceso' : 'En inicio (refuerzo)');
      if (prom < 11) tdDes.style.color = '#b91c1c';
    }
    tr.appendChild(tdDes);
    tbNotas.appendChild(tr);
  });

  if (cursosOrdenados.length) {
    const trTot = document.createElement('tr');
    trTot.style.background = '#f8fafc';
    trTot.style.borderTop = '2px solid #cbd5e1';
    const tdLbl = document.createElement('td');
    tdLbl.style.fontWeight = '700';
    tdLbl.textContent = 'Promedio por Bimestre';
    trTot.appendChild(tdLbl);

    const promsBim = [];
    [1, 2, 3, 4].forEach((b) => {
      const arr = sumBim[b];
      const p = arr.length ? (arr.reduce((acc, x) => acc + x, 0) / arr.length) : null;
      if (p !== null) promsBim.push(p);
      trTot.appendChild(crearCeldaNota(p, true));
    });
    const promFinal = promsBim.length ? (promsBim.reduce((acc, x) => acc + x, 0) / promsBim.length) : null;
    trTot.appendChild(crearCeldaNota(promFinal, true));
    const tdFin = document.createElement('td');
    tdFin.style.fontWeight = '600';
    tdFin.textContent = promFinal !== null ? (promFinal >= 14 ? 'Satisfactorio' : (promFinal >= 11 ? 'En progreso' : 'Requiere refuerzo')) : '--';
    trTot.appendChild(tdFin);
    tbNotas.appendChild(trTot);
  }

  const tbAsis = document.getElementById('tabla-asistencia-hijo');
  tbAsis.textContent = '';
  (d.asistencia || []).forEach((s) => {
    const tr = document.createElement('tr');
    const tdF = document.createElement('td');
    tdF.textContent = String(s.fecha).slice(0, 10);
    const tdE = document.createElement('td');
    const be = document.createElement('span');
    be.className = `badge ${s.estado === 'FALTA' ? 'badge-ROJO' : (s.estado === 'TARDANZA' ? 'badge-AMBAR' : 'badge-VERDE')}`;
    be.textContent = s.estado;
    tdE.appendChild(be);
    const tdH = document.createElement('td');
    tdH.textContent = s.hora_rfid ? String(s.hora_rfid).slice(0, 5) : 'Sin ingreso';
    tr.append(tdF, tdE, tdH);
    tbAsis.appendChild(tr);
  });

  const avisosEl = document.getElementById('lista-avisos-tutor');
  avisosEl.textContent = '';
  (d.alertas_recibidas || []).forEach((al) => {
    const box = document.createElement('div');
    box.className = 'protocol-card';
    box.style.borderColor = '#93c5fd';
    box.style.background = '#eff6ff';
    const top = document.createElement('div');
    top.style.display = 'flex';
    top.style.justifyContent = 'space-between';
    const tut = document.createElement('strong');
    tut.textContent = `✈ Alerta ${al.canal}`;
    const est = document.createElement('span');
    est.className = 'badge badge-GENERAL';
    est.textContent = String(al.fecha).slice(0, 10);
    top.append(tut, est);
    const p = document.createElement('p');
    p.style.marginTop = '6px';
    p.textContent = al.mensaje;
    box.append(top, p);
    avisosEl.appendChild(box);
  });
  (d.avisos_tutor || []).forEach((av) => {
    const box = document.createElement('div');
    box.className = 'protocol-card';
    const top = document.createElement('div');
    top.style.display = 'flex';
    top.style.justifyContent = 'space-between';
    const tut = document.createElement('strong');
    tut.textContent = av.tutor_nombre;
    const est = document.createElement('span');
    est.className = `badge badge-${av.estado}`;
    est.textContent = av.estado;
    top.append(tut, est);
    const p = document.createElement('p');
    p.style.marginTop = '6px';
    p.textContent = av.accion_acordada;
    box.append(top, p);
    avisosEl.appendChild(box);
  });
}

chatForm.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const texto = chatInput.value.trim();
  if (!texto) return;
  chatInput.value = '';
  await enviarConsulta(texto);
});

document.querySelectorAll('.chip').forEach((btn) => {
  btn.addEventListener('click', () => enviarConsulta(btn.dataset.prompt));
});

document.getElementById('btn-logout-padre').addEventListener('click', async () => {
  await fetch('/api/logout', { method: 'POST' });
  window.location.href = '/login.html';
});

const btnImp = document.getElementById('btn-imprimir-boleta');
if (btnImp) {
  btnImp.addEventListener('click', () => {
    const fEl = document.getElementById('print-fecha-boleta');
    if (fEl) fEl.textContent = `Emitido: ${new Date().toLocaleDateString('es-PE')}`;
    window.print();
  });
}

cargarPortalPadre();
