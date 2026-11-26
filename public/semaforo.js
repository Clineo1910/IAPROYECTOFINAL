let idsRojoPrevios = null;
let filtroGradoIot = 'TODOS';

function actualizarReloj() {
  const ahora = new Date();
  document.getElementById('iot-reloj').textContent = ahora.toLocaleTimeString('es-PE', { hour12: false });
  document.getElementById('iot-fecha').textContent = ahora.toLocaleDateString('es-PE', {
    weekday: 'long', day: '2-digit', month: 'short', year: 'numeric',
  });
}

async function refrescarSemaforo() {
  try {
    const iotKey = new URLSearchParams(window.location.search).get('iot_key');
    const url = iotKey ? `/api/dashboard?iot_key=${encodeURIComponent(iotKey)}` : '/api/dashboard';
    const r = await fetch(url);
    if (r.status === 401 || r.status === 403) {
      window.location.href = '/login.html';
      return;
    }
    const datos = await r.json();
    if (!r.ok) return;

    const todos = datos.alumnos || [];
    const filtrados = filtroGradoIot === 'TODOS' ? todos : todos.filter((a) => a.grado === filtroGradoIot);

    const rojos = filtrados.filter((a) => a.nivel_semaforo === 'ROJO');
    const ambars = filtrados.filter((a) => a.nivel_semaforo === 'AMBAR');
    const verdes = filtrados.filter((a) => a.nivel_semaforo === 'VERDE');

    document.getElementById('iot-total').textContent = filtrados.length;
    document.getElementById('iot-rojo').textContent = rojos.length;
    document.getElementById('iot-ambar').textContent = ambars.length;
    document.getElementById('iot-verde').textContent = verdes.length;
    document.getElementById('iot-prom-inst').textContent = `Índice prom: ${datos.resumen.promedio_riesgo}/100`;
    document.getElementById('iot-pct-verde').textContent = `${Math.round((verdes.length / Math.max(1, filtrados.length)) * 100)} % estable`;

    // Banner de nueva alerta roja en tiempo real (sobre el total global)
    const rojosGlobal = todos.filter((a) => a.nivel_semaforo === 'ROJO');
    const idsActuales = new Set(rojosGlobal.map((a) => a.alumno_id));
    const banner = document.getElementById('iot-alert-banner');
    const bannerTxt = document.getElementById('iot-alert-text');
    if (idsRojoPrevios !== null) {
      const nuevos = rojosGlobal.filter((a) => !idsRojoPrevios.has(a.alumno_id));
      if (nuevos.length > 0 && banner && bannerTxt) {
        bannerTxt.textContent = `🚨 NUEVA ALERTA ROJA DETECTADA POR RFID: ${nuevos.map((n) => `${n.nombre_completo} (Score ${n.indice_riesgo})`).join(', ')}`;
        banner.hidden = false;
      }
    }
    idsRojoPrevios = idsActuales;

    document.getElementById('cnt-rojo').textContent = `${rojos.length} casos`;
    document.getElementById('cnt-ambar').textContent = `${ambars.length} casos`;

    renderGradosStrip(todos);
    renderLista('lista-rojo', rojos, 'rojo');
    renderLista('lista-ambar', ambars, 'ambar');
    renderRfid(datos.ultimos_rfid || []);
    renderIntervencionesIot(datos.intervenciones || []);
  } catch (_err) {
    // Reintento automático
  }
}

function renderGradosStrip(todos) {
  const cont = document.getElementById('iot-grados-strip');
  if (!cont) return;
  cont.textContent = '';
  ['1ro Secundaria', '2do Secundaria', '3ro Secundaria', '4to Secundaria', '5to Secundaria'].forEach((g) => {
    const gr = todos.filter((a) => a.grado === g);
    const r = gr.filter((a) => a.nivel_semaforo === 'ROJO').length;
    const am = gr.filter((a) => a.nivel_semaforo === 'AMBAR').length;
    const card = document.createElement('div');
    card.style.background = 'rgba(30, 41, 59, 0.72)';
    card.style.border = r > 0 ? '1px solid rgba(239, 68, 68, 0.35)' : '1px solid rgba(148, 163, 184, 0.14)';
    card.style.borderRadius = '10px';
    card.style.padding = '10px 12px';
    card.style.display = 'flex';
    card.style.justifyContent = 'space-between';
    card.style.alignItems = 'center';

    const left = document.createElement('div');
    const t = document.createElement('strong');
    t.style.fontSize = '0.82rem';
    t.textContent = g.replace('Secundaria', 'Sec.');
    const sub = document.createElement('div');
    sub.style.fontSize = '0.72rem';
    sub.style.color = '#94a3b8';
    sub.textContent = `${gr.length} alumnos`;
    left.append(t, sub);

    const right = document.createElement('div');
    right.style.fontSize = '0.75rem';
    right.style.fontWeight = '700';
    right.style.color = r > 0 ? '#fca5a5' : (am > 0 ? '#fcd34d' : '#86efac');
    right.textContent = `${r} Rojo · ${am} Ámbar`;

    card.append(left, right);
    cont.appendChild(card);
  });
}

function renderLista(idContenedor, lista, clase) {
  const cont = document.getElementById(idContenedor);
  cont.textContent = '';
  if (lista.length === 0) {
    const p = document.createElement('p');
    p.style.color = '#94a3b8';
    p.textContent = 'Sin alertas activas en este nivel.';
    cont.appendChild(p);
    return;
  }

  lista.forEach((a) => {
    const card = document.createElement('div');
    card.className = `iot-card ${clase}`;

    const left = document.createElement('div');
    const h3 = document.createElement('h3');
    h3.textContent = a.nombre_completo;
    const meta = document.createElement('div');
    meta.className = 'iot-card-meta';
    meta.textContent = `${a.grado} ${a.seccion} · ${a.codigo_estudiante} · ${a.apoderado_nombre}`;

    const pills = document.createElement('div');
    pills.className = 'iot-pills';
    [
      `Faltas: ${a.metricas.faltas}`,
      `Prom: ${a.metricas.promedio_notas ?? '-'}`,
      `Convivencia: ${a.desglose ? a.desglose.convivencia_pts : 0} pts`,
    ].forEach((txt) => {
      const sp = document.createElement('span');
      sp.className = 'iot-pill';
      sp.textContent = txt;
      pills.appendChild(sp);
    });

    left.append(h3, meta, pills);
    const gauge = document.createElement('div');
    gauge.className = `iot-gauge ${clase}`;
    gauge.textContent = `${a.indice_riesgo}`;

    card.append(left, gauge);
    cont.appendChild(card);
  });
}

function renderRfid(eventos) {
  const cont = document.getElementById('lista-rfid');
  cont.textContent = '';
  eventos.slice(0, 6).forEach((e) => {
    const row = document.createElement('div');
    row.className = 'rfid-row';
    const left = document.createElement('div');
    const nom = document.createElement('strong'); nom.textContent = e.nombre_completo;
    const det = document.createElement('small');
    det.textContent = `${String(e.fecha).slice(0, 10)} · ${e.codigo_rfid} · ${e.grado} ${e.seccion}`;
    left.append(nom, det);
    const tag = document.createElement('span'); tag.className = `rfid-tag rfid-${e.estado}`; tag.textContent = e.estado;
    row.append(left, tag);
    cont.appendChild(row);
  });
}

function renderIntervencionesIot(lista) {
  const cont = document.getElementById('lista-iot-intervenciones');
  if (!cont) return;
  cont.textContent = '';
  lista.slice(0, 5).forEach((i) => {
    const row = document.createElement('div');
    row.className = 'rfid-row';
    const left = document.createElement('div');
    const nom = document.createElement('strong'); nom.textContent = `${i.nombre_completo} (${i.grado.replace('Secundaria', 'Sec.')})`;
    const det = document.createElement('small'); det.textContent = i.accion_acordada;
    left.append(nom, det);
    const tag = document.createElement('span');
    tag.className = `rfid-tag ${i.estado === 'REALIZADA' ? 'rfid-PRESENTE' : 'rfid-TARDANZA'}`;
    tag.textContent = i.estado;
    row.append(left, tag);
    cont.appendChild(row);
  });
}

document.getElementById('iot-filtro-grado')?.addEventListener('change', (e) => {
  filtroGradoIot = e.target.value;
  refrescarSemaforo();
});

actualizarReloj();
setInterval(actualizarReloj, 1000);
refrescarSemaforo();
setInterval(refrescarSemaforo, 4000);
