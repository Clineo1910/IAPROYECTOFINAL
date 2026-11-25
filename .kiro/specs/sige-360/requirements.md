# Requisitos — SIGE-360 (Sistema de Inteligencia Escolar Predictiva)

## 1. Propósito
Integrar un agente conversacional predictivo (**SIGE-Bot**) dentro de la aplicación web **SIGE-360** que detecte tempranamente riesgo de deserción y bajo rendimiento escolar cruzando 4 señales reales en PostgreSQL: asistencia RFID, notas, convivencia escolar y uso de biblioteca.

## 2. Requisitos Funcionales
- **RF-01 — Cálculo de índice de riesgo (0–100):** combinar asistencia (máx. 40 pts), notas (máx. 30 pts), convivencia (máx. 20 pts) y biblioteca (máx. 10 pts) para clasificar a cada estudiante en `ROJO` (≥ 60), `AMBAR` (30–59) o `VERDE` (< 30).
- **RF-02 — Herramientas MCP sobre PostgreSQL (mínimo 2; implementadas 5):**
  1. `calcular_indice_riesgo(alumno_id)`
  2. `listar_alumnos_en_riesgo(nivel, rol_usuario)`
  3. `consultar_historial_academico(busqueda, rol_usuario)`
  4. `consultar_protocolo_tutoria(tema)` *(RAG sobre reglamento interno y guías MINEDU)*
  5. `registrar_intervencion_tutorial(alumno_id, motivo, accion_acordada, rol_usuario, confirmado)`
- **RF-03 — Control de permisos por rol:**
  - `tutor`: consulta completa y registro de intervenciones previa confirmación explícita (`confirmado=True`).
  - `padre`: solo lectura del resumen académico/asistencia de su hijo, sin acceso al listado global ni a incidencias internas.
- **RF-04 — Chat integrado con memoria de sesión:** ventana de chat en `index.html` conectada vía `POST /api/chat` → Webhook n8n (Ruta A) manteniendo memoria por `sesion`.
- **RF-05 — Pantalla IoT Semáforo y Simulador RFID (Factor Wow):** vista dedicada `/semaforo.html` con auto-refresco cada 4 segundos y simulador de evento RFID (3 faltas seguidas + nota 06) que eleva la alerta en vivo y dispara la recomendación y mensaje al apoderado.

## 3. Requisitos No Funcionales y Cumplimiento Normativo
- **RNF-01 — Privacidad (Ley N.° 29733):** 100 % datos simulados; prohibido enviar datos reales de personas.
- **RNF-02 — Transparencia IA (Ley N.° 31814):** SIGE-Bot se identifica explícitamente como asistente de inteligencia artificial.
- **RNF-03 — Seguridad en BD y GitHub:** consultas SQL parametrizadas (`%s`), rol PostgreSQL `agente_sige` con `SELECT` + `INSERT` solo en `intervenciones_tutoriales`, y `.env` excluido en `.gitignore`.
