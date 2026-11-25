function actualizarReloj() {
  const ahora = new Date();
  document.getElementById('iot-reloj').textContent = ahora.toLocaleTimeString('es-PE', { hour12: false });
  document.getElementById('iot-fecha').textContent = ahora.toLocaleDateString('es-PE', {
    weekday: 'long', day: '2-digit', month: 'short', year: 'numeric',
  });
}

let idsRojoPrevios = null;

async function refrescarSemaforo() {
  try {
    const r = await fetch('/api/dashboard');
    const datos = await r.json();
    if (!r.ok) return;

    document.getElementById('iot-total').textContent = datos.resumen.total;
    document.getElementById('iot-rojo').textContent = datos.resumen.rojo;
    document.getElementById('iot-ambar').textContent = datos.resumen.ambar;
    document.getElementById('iot-verde').textContent = datos.resumen.verde;

    const rojos = datos.alumnos.filter((a) => a.nivel_semaforo === 'ROJO');
    const ambars = datos.alumnos.filter((a) => a.nivel_semaforo === 'AMBAR');

    const idsActuales = new Set(rojos.map((a) => a.alumno_id));
    const banner = document.getElementById('iot-alert-banner');
    const bannerTxt = document.getElementById('iot-alert-text');
    if (idsRojoPrevios !== null) {
      const nuevos = rojos.filter((a) => !idsRojoPrevios.has(a.alumno_id));
      if (nuevos.length > 0 && banner && bannerTxt) {
        bannerTxt.textContent = `🚨 NUEVA ALERTA ROJA DETECTADA POR RFID: ${nuevos.map((n) => `${n.nombre_completo} (Score ${n.indice_riesgo})`).join(', ')}`;
        banner.hidden = false;
      } else if (rojos.length <= 3 && banner) {
        banner.hidden = true;
      }
    }
    idsRojoPrevios = idsActuales;

    document.getElementById('cnt-rojo').textContent = `${rojos.length} casos`;
    document.getElementById('cnt-ambar').textContent = `${ambars.length} casos`;

    renderLista('lista-rojo', rojos, 'rojo');
    renderLista('lista-ambar', ambars, 'ambar');
    renderRfid(datos.ultimos_rfid || []);
  } catch (_err) {
    // Reintento automático
  }
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
    meta.textContent = `${a.grado} ${a.seccion} · ${a.codigo_estudiante} · Apoderado: ${a.apoderado_nombre}`;

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
  eventos.forEach((e) => {
    const row = document.createElement('div');
    row.className = 'rfid-row';

    const left = document.createElement('div');
    const nom = document.createElement('strong');
    nom.textContent = e.nombre_completo;
    const det = document.createElement('small');
    const fecha = String(e.fecha).slice(0, 10);
    det.textContent = `${fecha} · ${e.codigo_rfid} · ${e.grado} ${e.seccion}`;
    left.append(nom, det);

    const tag = document.createElement('span');
    tag.className = `rfid-tag rfid-${e.estado}`;
    tag.textContent = e.estado;

    row.append(left, tag);
    cont.appendChild(row);
  });
}

actualizarReloj();
setInterval(actualizarReloj, 1000);
refrescarSemaforo();
setInterval(refrescarSemaforo, 4000);
