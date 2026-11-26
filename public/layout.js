/**
 * layout.js - Shell compartido de SIGE-360 para arquitectura multipágina real.
 * Inyecta Sidebar con enlaces a páginas separadas, Topbar con sesión real y Panel SIGE-Bot + Rayos X MCP + Telegram.
 */

window.SIGE = {
  renderTextoSeguro(contenedor, texto) {
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
  },

  mostrarToast(id, texto) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = texto;
    el.hidden = false;
    setTimeout(() => { el.hidden = true; }, 4500);
  },

  hacerBuscable(selectId, placeholder = 'Buscar estudiante...') {
    const sel = document.getElementById(selectId);
    if (!sel || sel.dataset.buscable === '1') return;
    sel.dataset.buscable = '1';

    const todas = [...sel.options].map((o) => ({ value: o.value, text: o.textContent }));
    const norm = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

    const inp = document.createElement('input');
    inp.type = 'search';
    inp.placeholder = placeholder;
    inp.className = 'search-input';
    inp.style.width = '100%';
    inp.style.marginBottom = '5px';
    inp.style.padding = '6px 10px';
    inp.style.fontSize = '0.78rem';

    sel.parentNode.insertBefore(inp, sel);

    inp.addEventListener('input', () => {
      const q = norm(inp.value.trim());
      const prev = sel.value;
      sel.textContent = '';
      const filtradas = todas.filter((o) => !q || norm(o.text).includes(q));
      filtradas.forEach((o) => {
        const opt = document.createElement('option');
        opt.value = o.value;
        opt.textContent = o.text;
        sel.appendChild(opt);
      });
      if (filtradas.some((o) => o.value === prev)) {
        sel.value = prev;
      } else if (filtradas.length > 0) {
        sel.value = filtradas[0].value;
        sel.dispatchEvent(new Event('change'));
      }
    });
  },

  async enviarTelegram(mensaje, alumnoId = 3) {
    const r = await fetch('/api/alertas/telegram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alumno_id: alumnoId, mensaje }),
    });
    const d = await r.json();
    window.SIGE.agregarBurbuja('Telegram · Alertas SIGE-360', d.mensaje || 'Alerta procesada.', false, false);
  },

  agregarBurbuja(autor, texto, esUsuario, permitirTelegram = false) {
    const mensajesEl = document.getElementById('chat-mensajes');
    if (!mensajesEl) return null;
    const wrap = document.createElement('div');
    wrap.className = `bubble ${esUsuario ? 'bubble-user' : 'bubble-bot'}`;

    const meta = document.createElement('span');
    meta.className = 'bubble-meta';
    meta.textContent = autor;

    const body = document.createElement('span');
    window.SIGE.renderTextoSeguro(body, texto);
    wrap.append(meta, body);

    if (permitirTelegram) {
      const actions = document.createElement('div');
      actions.style.marginTop = '8px';
      const btnTg = document.createElement('button');
      btnTg.type = 'button';
      btnTg.className = 'btn btn-secondary btn-xs';
      btnTg.textContent = '✈ Enviar alerta por Telegram al apoderado';
      btnTg.addEventListener('click', () => window.SIGE.enviarTelegram(body.textContent, null));
      actions.appendChild(btnTg);
      wrap.appendChild(actions);
    }

    mensajesEl.appendChild(wrap);
    mensajesEl.scrollTop = mensajesEl.scrollHeight;
    return body;
  },

  async enviarConsultaAlAgente(texto) {
    window.SIGE.agregarBurbuja('Docente / Tutor', texto, true, false);
    const cuerpo = window.SIGE.agregarBurbuja('SIGE-Bot · Consultando MCP', 'Analizando datos en PostgreSQL...', false, false);
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
      window.SIGE.renderTextoSeguro(cuerpo, d.respuesta);

      // Botón 1-clic para reenviar por Telegram
      const wrap = cuerpo.parentElement;
      const actions = document.createElement('div');
      actions.style.marginTop = '8px';
      const btnTg = document.createElement('button');
      btnTg.type = 'button';
      btnTg.className = 'btn btn-secondary btn-xs';
      btnTg.textContent = '✈ Enviar por Telegram al apoderado';
      btnTg.addEventListener('click', () => window.SIGE.enviarTelegram(d.respuesta, null));
      actions.appendChild(btnTg);
      wrap.appendChild(actions);

      window.SIGE.cargarMcpLogs();
      if (typeof window.onChatCompleted === 'function') window.onChatCompleted();
    } catch (_err) {
      window.SIGE.renderTextoSeguro(cuerpo, 'No se pudo conectar con el servidor.');
    }
    const mensajesEl = document.getElementById('chat-mensajes');
    if (mensajesEl) mensajesEl.scrollTop = mensajesEl.scrollHeight;
  },

  async cargarMcpLogs() {
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
    } catch (_e) { /* silencioso */ }
  },

  async iniciarLayout({ paginaActiva, titulo }) {
    // 1. Verificar sesión docente
    const rMe = await fetch('/api/me');
    if (!rMe.ok) {
      window.location.href = '/login.html';
      return;
    }
    const me = await rMe.json();
    if (me.usuario?.rol === 'padre') {
      window.location.href = '/padres.html';
      return;
    }

    // 2. Renderizar Sidebar multipágina
    const sidebar = document.getElementById('sige-sidebar');
    if (sidebar) {
      const links = [
        ['panel', '/', 'Panel Predictivo'],
        ['estudiantes', '/estudiantes.html', 'Directorio de Estudiantes'],
        ['notas', '/notas.html', 'Registro de Notas'],
        ['convivencia', '/convivencia.html', 'Convivencia Escolar'],
        ['biblioteca', '/biblioteca.html', 'Biblioteca Escolar'],
        ['intervenciones', '/intervenciones.html', 'Intervenciones Tutoriales'],
        ['usuarios', '/usuarios.html', 'Alumnos y Cuentas de Padres'],
        ['protocolos', '/protocolos.html', 'Protocolos MINEDU (RAG)'],
      ];

      sidebar.textContent = '';
      const topDiv = document.createElement('div');

      const brand = document.createElement('div');
      brand.className = 'sidebar-brand';
      const logo = document.createElement('div');
      logo.className = 'brand-logo';
      logo.textContent = '360';
      const bText = document.createElement('div');
      const h1 = document.createElement('h1');
      h1.textContent = 'SIGE-360';
      const sp = document.createElement('span');
      sp.textContent = 'I.E. Demo · Año Escolar 2026';
      bText.append(h1, sp);
      brand.append(logo, bText);

      const nav = document.createElement('nav');
      nav.className = 'nav-section';
      const lbl1 = document.createElement('div');
      lbl1.className = 'nav-label';
      lbl1.textContent = 'Módulos del Sistema';
      nav.appendChild(lbl1);

      links.forEach(([key, href, label]) => {
        const a = document.createElement('a');
        a.href = href;
        a.className = `nav-btn${key === paginaActiva ? ' active' : ''}`;
        a.textContent = label;
        nav.appendChild(a);
      });

      const lbl2 = document.createElement('div');
      lbl2.className = 'nav-label';
      lbl2.style.marginTop = '12px';
      lbl2.textContent = 'IoT / Sala de Profesores';
      nav.appendChild(lbl2);

      const aIot = document.createElement('a');
      aIot.href = '/semaforo.html';
      aIot.target = '_blank';
      aIot.rel = 'noopener';
      aIot.className = 'nav-btn';
      aIot.textContent = 'Pantalla Semáforo en Vivo ↗';
      nav.appendChild(aIot);

      topDiv.append(brand, nav);

      const foot = document.createElement('div');
      foot.className = 'sidebar-footer';
      const st = document.createElement('strong');
      st.textContent = 'Cumplimiento Normativo';
      foot.append(st, document.createTextNode('Datos 100% simulados (Ley N.° 29733). Asistente IA transparente (Ley N.° 31814). PostgreSQL + MCP + n8n + Telegram.'));

      sidebar.append(topDiv, foot);
    }

    // 3. Renderizar Topbar
    const topbar = document.getElementById('sige-topbar');
    if (topbar) {
      topbar.textContent = '';
      const left = document.createElement('div');
      left.className = 'topbar-left';
      const h2 = document.createElement('h2');
      h2.className = 'page-title';
      h2.textContent = titulo;
      const badge = document.createElement('span');
      badge.className = 'live-badge';
      const dot = document.createElement('span');
      dot.className = 'pulse-dot';
      badge.append(dot, document.createTextNode(' PostgreSQL + MCP Activo'));
      left.append(h2, badge);

      const right = document.createElement('div');
      right.className = 'topbar-right';
      const userPill = document.createElement('span');
      userPill.className = 'badge badge-GENERAL';
      userPill.textContent = `Docente · ${me.usuario.nombre}`;

      const btnPdf = document.createElement('button');
      btnPdf.type = 'button';
      btnPdf.className = 'btn btn-secondary';
      btnPdf.textContent = 'Exportar PDF';
      btnPdf.addEventListener('click', () => window.print());

      const btnIot = document.createElement('a');
      btnIot.href = '/semaforo.html';
      btnIot.target = '_blank';
      btnIot.rel = 'noopener';
      btnIot.className = 'btn btn-dark';
      btnIot.textContent = 'Pantalla IoT ↗';

      const btnOut = document.createElement('button');
      btnOut.type = 'button';
      btnOut.className = 'btn btn-secondary';
      btnOut.textContent = 'Cerrar sesión';
      btnOut.addEventListener('click', async () => {
        await fetch('/api/logout', { method: 'POST' });
        window.location.href = '/login.html';
      });

      right.append(userPill, btnPdf, btnIot, btnOut);
      topbar.append(left, right);
    }

    // 4. Renderizar Panel de Chat SIGE-Bot + Rayos X MCP
    const chatHost = document.getElementById('sige-chat-panel');
    if (chatHost) {
      chatHost.textContent = '';
      const head = document.createElement('div');
      head.className = 'chat-head';
      const ag = document.createElement('div');
      ag.className = 'chat-agent';
      const av = document.createElement('div');
      av.className = 'chat-avatar';
      av.textContent = 'IA';
      const agTxt = document.createElement('div');
      const strong = document.createElement('strong');
      strong.textContent = 'SIGE-Bot · Asistente Predictivo';
      const small = document.createElement('small');
      small.textContent = '6 herramientas MCP · Telegram activo';
      agTxt.append(strong, small);
      ag.append(av, agTxt);
      const pd = document.createElement('span');
      pd.className = 'pulse-dot';
      head.append(ag, pd);

      const msgs = document.createElement('div');
      msgs.id = 'chat-mensajes';
      msgs.className = 'chat-messages';

      const chips = document.createElement('div');
      chips.className = 'chat-chips';
      [
        ['¿Quiénes están en riesgo hoy?', '¿Qué alumnos están en alerta roja y necesitan atención urgente hoy?'],
        ['Desaprobados por curso', 'Lístame los estudiantes con notas menores a 11 y en qué cursos están así'],
        ['Reporte de Mateo Quispe', 'Dame el historial completo, notas, faltas y convivencia de Mateo Quispe'],
        ['Caso Diego Huamán', '¿Cuál es la situación actual y qué intervenciones tiene Diego Huamán?'],
        ['Protocolo 3 faltas', '¿Qué indica el protocolo MINEDU cuando un alumno falta 3 días seguidos?'],
        ['Protocolo aislamiento', '¿Qué protocolo de convivencia aplico si un alumno presenta aislamiento en clase?'],
        ['Registrar intervención', 'Registra una intervención tutorial para Lucas Mendoza (ID 3) por seguimiento en Matemática con refuerzo los miércoles'],
      ].forEach(([lbl, prompt]) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'chip';
        b.textContent = lbl;
        b.addEventListener('click', () => window.SIGE.enviarConsultaAlAgente(prompt));
        chips.appendChild(b);
      });

      const form = document.createElement('form');
      form.className = 'chat-form';
      const inp = document.createElement('input');
      inp.id = 'chat-texto';
      inp.type = 'text';
      inp.placeholder = 'Escribe tu consulta para SIGE-Bot...';
      inp.maxLength = 500;
      inp.required = true;
      inp.autocomplete = 'off';
      const btn = document.createElement('button');
      btn.type = 'submit';
      btn.className = 'btn btn-primary';
      btn.textContent = 'Enviar';
      form.append(inp, btn);
      form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const txt = inp.value.trim();
        if (!txt) return;
        inp.value = '';
        await window.SIGE.enviarConsultaAlAgente(txt);
      });

      chatHost.append(head, msgs, chips, form);
      window.SIGE.agregarBurbuja(
        'SIGE-Bot · IA Preventiva (Ley N.° 31814)',
        'Hola, soy el asistente de inteligencia artificial de SIGE-360. Consulto en tiempo real notas, asistencia RFID, convivencia, biblioteca y protocolos MINEDU.',
        false,
        false
      );
    }
  },
};
