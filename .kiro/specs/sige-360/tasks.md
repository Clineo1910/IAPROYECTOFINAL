# Plan de Tareas — SIGE-360

- [x] **1. Base de datos PostgreSQL simulada**
  - Crear `database/sige360_postgres.sql` con 7 tablas y datos simulados creíbles.
  - Crear `database/crear_usuario_agente_postgres.sql` con el rol de privilegios mínimos `agente_sige`.
- [x] **2. Servidor MCP en Python (`agente/servidor_mcp.py`)**
  - Implementar 5 herramientas MCP con `FastMCP` (`mcp[cli]<2`) y `transport='streamable-http'` en `http://127.0.0.1:8000/mcp`.
  - Verificar consultas parametrizadas (`%s`), `LIMIT` y validación de permisos `tutor`/`padre`.
- [x] **3. Flujo de agente en n8n (Ruta A)**
  - Exportar `agente/n8n_workflow_sige360.json` con Webhook, AI Agent, Gemini (`models/gemini-flash-lite-latest`), Simple Memory por `sesion`, MCP Client Tool (`httpStreamable`) y Respond to Webhook.
  - Redactar `agente/instrucciones.txt` con reglas de transparencia (Ley 31814) y privacidad (Ley 29733).
- [x] **4. Aplicación web de producción y pantalla IoT**
  - Construir `app.py` (FastAPI + Uvicorn en puerto `3060`) con `/api/dashboard`, `/api/alumno/{id}`, `/api/protocolos`, `/api/simular-rfid`, `/api/reset-demo` y `/api/chat`.
  - Diseñar `public/index.html` (sidebar, KPIs, Ficha 360°, protocolos RAG, intervenciones y chat integrado) y `public/semaforo.html` (pantalla IoT Sala de Profesores).
- [x] **5. Validación y documentación de entrega**
  - Completar `docs/ficha_agente.md`, `docs/casos_de_prueba.md` (10/10 aprobados en vivo), `docs/guion_demo_3min.md` y `README.md`.
  - Verificar que `.env` esté excluido en `.gitignore` y sin claves en el repositorio.
