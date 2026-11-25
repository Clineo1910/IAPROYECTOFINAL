# Diseño de Arquitectura — SIGE-360

## 1. Vista General
```text
Navegador (index.html / semaforo.html)
  └── POST /api/chat { mensaje }
        ▼
Backend Web Python (app.py — FastAPI + Uvicorn :3060)
  └── POST http://localhost:5678/webhook/agente { sesion, rol, mensaje }
        ▼
Orquestador n8n (Ruta A: Webhook → AI Agent + Gemini Flash-Lite + Simple Memory → Respond)
  └── MCP Client Tool (HTTP Streamable → http://127.0.0.1:8000/mcp)
        ▼
Servidor MCP Python (agente/servidor_mcp.py — FastMCP)
  └── Consultas SQL parametrizadas (usuario agente_sige)
        ▼
PostgreSQL 18 (BD sige360 — UTF-8)
```

## 2. Modelo de Datos (`database/sige360_postgres.sql`)
- `alumnos` (20 registros simulados, con `codigo_estudiante` y `codigo_rfid`)
- `notas` (40 registros, escala 0–20)
- `asistencia` (34 registros, estados `PRESENTE` / `TARDANZA` / `FALTA`, origen `RFID_PUERTA`)
- `incidencias_convivencia` (16 registros, gravedad `BAJA` / `MEDIA` / `ALTA`)
- `biblioteca_uso` (16 registros)
- `intervenciones_tutoriales` (15 registros; única tabla con permiso `INSERT` para el agente)
- `protocolos_minedu` (15 documentos de reglamento interno y guías de alerta temprana)

## 3. Fórmula del Motor Predictivo
- **Asistencia (0–40):** `min(40, faltas * 10 + tardanzas * 3)`
- **Notas (0–30):** `<11 → 30`, `11–12.99 → 18`, `13–13.99 → 10`, `≥14 → 0`
- **Convivencia (0–20):** `min(20, alta * 12 + media * 7 + baja * 3)` *(excluye reconocimientos)*
- **Biblioteca (0–10):** `min(10, no_devuelto * 10 + devolucion_tardia * 5)`
- **Semáforo:** `ROJO` (≥ 60), `AMBAR` (30–59), `VERDE` (< 30)

## 4. Contrato del Puente de Chat
- **Entrada a n8n:** `{"sesion": "<cookie_sid>", "rol": "tutor|padre", "mensaje": "<consulta>"}`
- **Salida de n8n:** `{"respuesta": "<texto verificado>"}`
- **Prevención XSS:** el cliente web (`public/app.js`) renderiza mensajes únicamente con `document.createTextNode()` y `textContent`, nunca `innerHTML`.
