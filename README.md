# SIGE-360 — Sistema de Inteligencia Escolar Predictiva

Plataforma escolar multipágina en **Python (FastAPI + Uvicorn)** con **PostgreSQL 18**, **6 herramientas MCP en Python** (`mcp[cli]<2` / `FastMCP` sobre `streamable-http`), agente conversacional en **n8n (Ruta A)** con **Google Gemini**, **Pantalla IoT Semáforo** y **alertas en vivo por Telegram** (`@SIGE360_Alertas_Bot`).

## Arquitectura del proyecto

```text
Navegador (Portal Docente multipágina / Portal Padres / Pantalla IoT)
    │  Cookie de sesión RBAC + POST /api/chat
    ▼
Backend Web Python (app.py - FastAPI :3060 + Auth RBAC + Telegram Bot API)
    │  POST { sesion, rol, mensaje }
    ▼
Agente en n8n (Webhook → AI Agent + Gemini Flash-Lite + Simple Memory → Respond)
    │  MCP Client Tool (HTTP Streamable → http://127.0.0.1:8000/mcp)
    ▼
Servidor MCP Python (agente/servidor_mcp.py - 6 herramientas + Rayos X MCP)
    │  Consultas SQL parametrizadas (%s) con rol agente_sige
    ▼
Base de datos PostgreSQL 18 (sige360 - datos 100% simulados)
```

## Cuentas de acceso (Login en `http://localhost:3060/login.html`)

| Rol | Correo | Contraseña | Acceso |
| :--- | :--- | :--- | :--- |
| **Docente / Tutor** | `docente@sige360.edu.pe` | `docente2026` | Portal Docente completo (`/`, `/notas.html`, `/convivencia.html`, `/biblioteca.html`, `/intervenciones.html`, `/usuarios.html`, `/protocolos.html`) |
| **Padre / Apoderado** | `padre@sige360.edu.pe` | `padre2026` | Portal de Familias (`/padres.html`), solo lectura de su hijo (`403` / redirección en rutas docentes) |

## Páginas del sistema (`public/`)
- `login.html` — Autenticación RBAC contra tabla `usuarios` de PostgreSQL.
- `index.html` — Panel Predictivo (KPIs, gráfico por grado, Factor Wow RFID, Ficha 360°, chat SIGE-Bot + Rayos X MCP).
- `notas.html` — Libreta ponderada editable por Grado, Curso y Bimestre (`N1–N4 40%`, `Ex. Parcial 30%`, `Ex. Final 30%` → `Nota Final`, 480 notas).
- `convivencia.html` — Registro e historial de incidencias de convivencia escolar.
- `biblioteca.html` — Registro e historial de préstamos y devoluciones.
- `intervenciones.html` — Gestión de intervenciones tutoriales y envío de alertas Telegram.
- `usuarios.html` — Matrícula de estudiantes y creación de cuentas de padres + auto-vinculación Telegram.
- `protocolos.html` — Visor buscable de los 15 protocolos internos y guías MINEDU (RAG).
- `padres.html` — Portal exclusivo de familias (boleta, asistencia RFID, alertas y SIGE-Bot bloqueado en rol `padre`).
- `semaforo.html` — Pantalla IoT de Sala de Profesores (auto-refresco cada 4 segundos).

## Orden de encendido (para clase y feria)

1. **PostgreSQL 18** activo (puerto `5432`) con `database/sige360_postgres.sql` y `database/crear_usuario_agente_postgres.sql` cargados.
2. **Servidor MCP en Python** (Terminal 1):
   ```bash
   python agente/servidor_mcp.py
   ```
   Escucha en `http://127.0.0.1:8000/mcp`.
3. **n8n local** (Terminal 2):
   ```bash
   npx n8n
   ```
   Importa `agente/n8n_workflow_sige360.json`, vincula tu credencial de Gemini (`Gemini Flash-Lite Latest`) y **Publica / Activa** el flujo.
4. **Aplicación web SIGE-360** (Terminal 3):
   ```bash
   uvicorn app:app --port 3060
   ```
   *(Sin `--reload` en Windows).* Abre `http://localhost:3060` y `http://localhost:3060/semaforo.html`.

## Seguridad y cumplimiento normativo
- **Sin claves en GitHub:** `.env` (PostgreSQL + Telegram) está bloqueado en `.gitignore`; la API key de Gemini vive solo en n8n.
- **Privilegios mínimos en BD:** `agente_sige` solo tiene `SELECT` en todas las tablas e `INSERT` únicamente en `intervenciones_tutoriales` (jamás `UPDATE` ni `DELETE`).
- **Confirmación humana:** `registrar_intervencion_tutorial` exige `confirmado=True` tras confirmar con el tutor.
- **Datos 100 % simulados (Ley N.° 29733)** y **transparencia IA (Ley N.° 31814)**.
