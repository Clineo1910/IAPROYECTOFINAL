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

  const badge = document.getElementById('hijo-estado-badge');
  badge.className = `badge badge-${a.nivel_semaforo}`;
  badge.textContent = a.nivel_semaforo === 'ROJO'
    ? 'Requiere apoyo prioritario'
    : (a.nivel_semaforo === 'AMBAR' ? 'En seguimiento preventivo' : 'Desempeño estable');

  const tbNotas = document.getElementById('tabla-notas-hijo');
  tbNotas.textContent = '';
  (d.notas || []).forEach((n) => {
    const tr = document.createElement('tr');
    [n.curso, `Bim. ${n.bimestre}`].forEach((v) => {
      const td = document.createElement('td');
      td.textContent = v;
      tr.appendChild(td);
    });
    const tdN = document.createElement('td');
    const bn = document.createElement('span');
    bn.className = `badge ${n.nota < 11 ? 'badge-ROJO' : (n.nota < 14 ? 'badge-AMBAR' : 'badge-VERDE')}`;
    bn.textContent = Number(n.nota).toFixed(1);
    tdN.appendChild(bn);
    tr.appendChild(tdN);

    const tdDes = document.createElement('td');
    tdDes.textContent = n.nota >= 14 ? 'Logro esperado' : (n.nota >= 11 ? 'En proceso' : 'En inicio (refuerzo)');
    tr.appendChild(tdDes);

    const tdF = document.createElement('td');
    tdF.textContent = String(n.fecha_registro).slice(0, 10);
    tr.appendChild(tdF);
    tbNotas.appendChild(tr);
  });

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

cargarPortalPadre();
